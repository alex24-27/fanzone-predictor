import os
import re
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'super_secret_sports_key'
DB_FILE = 'database.db'
TEAM_PICK_CAP = 5

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            score INTEGER DEFAULT 0
        )
    ''')
    
    # Create Games Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            league TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            game_date TEXT NOT NULL,
            status TEXT DEFAULT 'SCHEDULED',
            outcome TEXT DEFAULT NULL,
            home_score INTEGER DEFAULT 0,
            away_score INTEGER DEFAULT 0
        )
    ''')
    
    # Create Predictions Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            predicted_winner TEXT NOT NULL,
            UNIQUE(user_id, game_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(game_id) REFERENCES games(id)
        )
    ''')
    
    conn.commit()
    conn.close()


def _get_active_pick_count_map(conn, game_ids):
    if not game_ids:
        return {}

    placeholders = ','.join(['?'] * len(game_ids))
    rows = conn.execute(f'''
        SELECT p.game_id, p.predicted_winner, COUNT(*) AS pick_count
        FROM predictions p
        JOIN games g ON p.game_id = g.id
        WHERE p.game_id IN ({placeholders})
          AND (g.outcome IS NULL OR g.outcome = '')
        GROUP BY p.game_id, p.predicted_winner
    ''', tuple(game_ids)).fetchall()

    count_map = {}
    for row in rows:
        game_map = count_map.setdefault(row['game_id'], {})
        game_map[row['predicted_winner']] = row['pick_count']
    return count_map


def _build_game_cap_state(game, count_map, user_pick=None):
    game_id = game['id'] if 'id' in game.keys() else game['game_id']
    game_counts = count_map.get(game_id, {})
    home_count = game_counts.get(game['home_team'], 0)
    away_count = game_counts.get(game['away_team'], 0)

    home_full = home_count >= TEAM_PICK_CAP
    away_full = away_count >= TEAM_PICK_CAP
    both_full = home_full and away_full

    picker_locked_for_user = False
    if user_pick == game['home_team'] and away_full:
        picker_locked_for_user = True
    elif user_pick == game['away_team'] and home_full:
        picker_locked_for_user = True
    elif not user_pick and both_full:
        picker_locked_for_user = True

    return {
        'home_count': home_count,
        'away_count': away_count,
        'home_full': home_full,
        'away_full': away_full,
        'both_full': both_full,
        'picker_locked_for_user': picker_locked_for_user,
    }


def _get_pick_rejection_message(game, cap_state, existing_pick, attempted_pick):
    if attempted_pick == existing_pick:
        return None

    if cap_state['both_full']:
        return f"This event is locked. Both teams have reached the {TEAM_PICK_CAP}-user limit."

    if cap_state['picker_locked_for_user']:
        return (
            f"You cannot switch picks because the opposite team already has "
            f"{TEAM_PICK_CAP} users."
        )

    if attempted_pick == game['home_team'] and cap_state['home_full']:
        return f"{game['home_team']} has reached the {TEAM_PICK_CAP}-user pick limit."

    if attempted_pick == game['away_team'] and cap_state['away_full']:
        return f"{game['away_team']} has reached the {TEAM_PICK_CAP}-user pick limit."

    return None

# Authentication Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        # Enforce backend validation rules
        if len(password) < 12 or not re.search("[A-Z]", password) or not re.search("[a-z]", password) or not re.search(r"[\d\W_]", password):
            flash("Password does not meet required strength rules.", "danger")
            return redirect(url_for('register'))
        
        if "password" in password.lower() or username.lower() in password.lower():
            flash("Password contains restricted common phrases.", "danger")
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password, method='scrypt')
        
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.', 'danger')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/api/check-username', methods=['POST'])
def check_username():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    
    # Return false immediately for short or empty entries to prevent premature errors
    if not username:
        return jsonify({'exists': False})
        
    conn = get_db_connection()
    # Check if the username exists in the users table (case-insensitive)
    user_record = conn.execute(
        "SELECT id FROM users WHERE LOWER(username) = LOWER(?)", 
        (username,)
    ).fetchone()
    conn.close()
    
    # Send a JSON response back to the client browser script
    return jsonify({'exists': user_record is not None})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Core Prediction Engine Route
@app.route('/')
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()

    # Track the active filters across render operations (Default to all sports active)
    saved_filters = ['football', 'basketball', 'soccer', 'baseball', 'hockey']
    
    if request.method == 'POST':
        game_id = request.form.get('game_id')
        predicted_winner = request.form.get('predicted_winner') # Uses .get() to prevent crashes

        # Capture the raw comma-separated filter string from the form submission
        raw_filters = request.form.get('active_filters', '')
        if raw_filters:
            saved_filters = raw_filters.split(',')
        
        # Security Fail-Safe Check: reject if empty or missing entirely
        if not game_id or not predicted_winner:
            error_msg = 'Error: You must pick a winning team before submitting.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                conn.close()
                return jsonify({'status': 'error', 'message': error_msg}), 400
            flash(error_msg, 'danger')
            return redirect(url_for('dashboard'))
            
        # Security Check: Fetch game details and validate valid team selection
        game = conn.execute('''
            SELECT id, home_team, away_team, game_date, outcome
            FROM games
            WHERE id = ?
        ''', (game_id,)).fetchone()
        if not game:
            conn.close()
            error_msg = 'Selected event does not exist.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': error_msg}), 404
            flash(error_msg, 'danger')
            return redirect(url_for('dashboard'))

        if predicted_winner not in (game['home_team'], game['away_team']):
            conn.close()
            error_msg = 'Invalid selection for this matchup.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': error_msg}), 400
            flash(error_msg, 'danger')
            return redirect(url_for('dashboard'))

        if game['outcome'] not in (None, ''):
            conn.close()
            error_msg = 'Submission rejected! This event is no longer active.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': error_msg}), 403
            flash(error_msg, 'danger')
            return redirect(url_for('dashboard'))
        
        if game:
            kickoff_str = game['game_date'].replace('Z', '')
            kickoff_datetime = datetime.fromisoformat(kickoff_str)
            
            if datetime.utcnow() >= kickoff_datetime:
                conn.close()
                error_msg = 'Submission rejected! This game has already kicked off.'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'status': 'error', 'message': error_msg}), 403
                flash(error_msg, 'danger')
                return redirect(url_for('dashboard'))

        existing_row = conn.execute('''
            SELECT predicted_winner
            FROM predictions
            WHERE user_id = ? AND game_id = ?
        ''', (session['user_id'], game_id)).fetchone()
        existing_pick = existing_row['predicted_winner'] if existing_row else None

        count_map = _get_active_pick_count_map(conn, [game['id']])
        cap_state = _build_game_cap_state(game, count_map, existing_pick)
        rejection_message = _get_pick_rejection_message(game, cap_state, existing_pick, predicted_winner)

        if rejection_message:
            conn.close()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': rejection_message}), 403
            flash(rejection_message, 'danger')
            return redirect(url_for('dashboard'))
        
        # Save or update user selection safely
        conn.execute('''
            INSERT INTO predictions (user_id, game_id, predicted_winner)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, game_id) DO UPDATE SET predicted_winner=excluded.predicted_winner
        ''', (session['user_id'], game_id, predicted_winner))
        conn.commit()
        # Check if this is an asynchronous AJAX background request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            conn.close()
            return jsonify({'status': 'success', 'game_id': game_id})
        flash('Prediction updated successfully!', 'success')


    # Fetch matches and any predictions this specific user already saved
    # Fetch all matches sorted from earliest kickoff to latest kickoff by default
    # Fetch only upcoming matches (where an official winner has not been set)
    query = """
        SELECT * FROM games 
        WHERE outcome IS NULL OR outcome = ''
        ORDER BY datetime(game_date) ASC
    """
    games = conn.execute(query).fetchall()

    user_preds = conn.execute('SELECT game_id, predicted_winner FROM predictions WHERE user_id = ?', (session['user_id'],)).fetchall()

    game_ids = [game['id'] for game in games]
    count_map = _get_active_pick_count_map(conn, game_ids)

    pred_dict = {p['game_id']: p['predicted_winner'] for p in user_preds}
    cap_info = {}
    for game in games:
        user_pick = pred_dict.get(game['id'])
        cap_info[game['id']] = _build_game_cap_state(game, count_map, user_pick)

    conn.close()
    
    # Send active filter criteria back to frontend state mapping
    return render_template(
        'dashboard.html',
        games=games,
        predictions=pred_dict,
        saved_filters=saved_filters,
        cap_info=cap_info,
        team_pick_cap=TEAM_PICK_CAP,
    )

@app.route('/active-picks', methods=['GET', 'POST'])
def active_picks():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    if request.method == 'POST':
        game_id = request.form.get('game_id')
        predicted_winner = request.form.get('predicted_winner')

        if not game_id or not predicted_winner:
            error_msg = 'Error: Please choose a team before saving.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                conn.close()
                return jsonify({'status': 'error', 'message': error_msg}), 400
            flash(error_msg, 'danger')
            return redirect(url_for('active_picks'))

        # Verify this game belongs to an active pick and has not locked yet.
        game = conn.execute('''
            SELECT g.id, g.home_team, g.away_team, g.game_date
            FROM predictions p
            JOIN games g ON p.game_id = g.id
            WHERE p.user_id = ?
              AND p.game_id = ?
              AND (g.outcome IS NULL OR g.outcome = '')
        ''', (session['user_id'], game_id)).fetchone()

        if not game:
            conn.close()
            error_msg = 'This pick is no longer active or does not belong to your account.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': error_msg}), 403
            flash(error_msg, 'danger')
            return redirect(url_for('active_picks'))

        if predicted_winner not in (game['home_team'], game['away_team']):
            conn.close()
            error_msg = 'Invalid selection for this matchup.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': error_msg}), 400
            flash(error_msg, 'danger')
            return redirect(url_for('active_picks'))

        kickoff_str = game['game_date'].replace('Z', '')
        kickoff_datetime = datetime.fromisoformat(kickoff_str)

        if datetime.utcnow() >= kickoff_datetime:
            conn.close()
            error_msg = 'Submission rejected! This event has already started.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': error_msg}), 403
            flash(error_msg, 'danger')
            return redirect(url_for('active_picks'))

        existing_row = conn.execute('''
            SELECT predicted_winner
            FROM predictions
            WHERE user_id = ? AND game_id = ?
        ''', (session['user_id'], game_id)).fetchone()
        existing_pick = existing_row['predicted_winner'] if existing_row else None

        count_map = _get_active_pick_count_map(conn, [game['id']])
        cap_state = _build_game_cap_state(game, count_map, existing_pick)
        rejection_message = _get_pick_rejection_message(game, cap_state, existing_pick, predicted_winner)

        if rejection_message:
            conn.close()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': rejection_message}), 403
            flash(rejection_message, 'danger')
            return redirect(url_for('active_picks'))

        conn.execute('''
            UPDATE predictions
            SET predicted_winner = ?
            WHERE user_id = ? AND game_id = ?
        ''', (predicted_winner, session['user_id'], game_id))
        conn.commit()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            conn.close()
            return jsonify({'status': 'success', 'game_id': game_id})

        flash('Pick updated successfully!', 'success')

    active_pick_rows = conn.execute('''
        SELECT
            p.game_id,
            p.predicted_winner,
            g.league,
            g.home_team,
            g.away_team,
            g.game_date,
            g.status
        FROM predictions p
        JOIN games g ON p.game_id = g.id
        WHERE p.user_id = ?
          AND (g.outcome IS NULL OR g.outcome = '')
        ORDER BY datetime(g.game_date) ASC
    ''', (session['user_id'],)).fetchall()

    game_ids = [pick['game_id'] for pick in active_pick_rows]
    count_map = _get_active_pick_count_map(conn, game_ids)

    cap_info = {}
    for pick in active_pick_rows:
        cap_info[pick['game_id']] = _build_game_cap_state(pick, count_map, pick['predicted_winner'])

    conn.close()

    return render_template(
        'active_picks.html',
        active_picks=active_pick_rows,
        cap_info=cap_info,
        team_pick_cap=TEAM_PICK_CAP,
    )

@app.route('/leaderboard')
def leaderboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    # Fetch all users sorted by score in descending order
    users = conn.execute('SELECT username, score FROM users ORDER BY score DESC').fetchall()
    conn.close()
    
    return render_template('leaderboard.html', users=users)

@app.route('/analytics')
def analytics():
    # Retrieve the unique database ID for the currently active browser session
    user_id = session.get('user_id')
    
    # Safety Lock: Redirect unauthenticated guests to the login screen
    if not user_id:
        flash("Please log in to view your personalized pick history.", "warning")
        return redirect(url_for('login')) 
    
    conn = get_db_connection()
    
    # Fetch all records where a match is finished and an outcome is recorded
    metrics_query = """
        SELECT p.predicted_winner, g.outcome, g.league 
        FROM predictions p
        JOIN games g ON p.game_id = g.id
        WHERE p.user_id = ? AND g.outcome IS NOT NULL AND g.outcome != ''
    """
    history = conn.execute(metrics_query, (user_id,)).fetchall()

    # Initial overall record counters
    total_correct = 0
    total_incorrect = 0
    total_pushed = 0 # New counter to track pushed outcomes independently

    # Categorized sport counters for the bar chart visual tracking metrics
    sport_data = {
        'football': 0,
        'basketball': 0,
        'soccer': 0,
        'baseball': 0,
        'hockey': 0
    }

    for row in history:
        # Determine specific broad sports vertical from league metadata string
        league_lower = row['league'].lower()
        if 'football' in league_lower: sport_cat = 'football'
        elif 'basketball' in league_lower: sport_cat = 'basketball'
        elif 'soccer' in league_lower or 'cup' in league_lower: sport_cat = 'soccer'
        elif 'baseball' in league_lower or 'mlb' in league_lower: sport_cat = 'baseball'
        elif 'hockey' in league_lower or 'nhl' in league_lower: sport_cat = 'hockey'
        else: sport_cat = None

        # EVALUATE FOR PUSHED OUTCOMES
        if row['outcome'] == 'Draw':
            total_pushed += 1
            # Skip adding to total_correct or total_incorrect so pushes don't hurt or help stats
            continue

        # EVALUATE STANDARD WIN / LOSS SELECTIONS
        # Compare pick selection string against actual stored master matrix result
        if row['predicted_winner'] == row['outcome']:
            total_correct += 1
            if sport_cat:
                sport_data[sport_cat] += 1
        else:
            total_incorrect += 1

    # Only count matches that actually resulted in a win or loss when calculating win percentage
    settled_decisions = total_correct + total_incorrect
    win_percentage = round((total_correct / settled_decisions) * 100, 1) if settled_decisions > 0 else 0
    
    # Total picks represents all settled entries including pushes
    total_picks = settled_decisions + total_pushed 

    # LOG QUERY: Fetch ALL user predictions alongside live scoring columns
    log_query = """
        SELECT 
            g.league, g.home_team, g.away_team, g.game_date,
            g.home_score, g.away_score, g.outcome,
            p.predicted_winner
        FROM predictions p
        JOIN games g ON p.game_id = g.id
        WHERE p.user_id = ?
        ORDER BY datetime(g.game_date) DESC
    """
    prediction_log = conn.execute(log_query, (user_id,)).fetchall()
    conn.close()

    return render_template(
        'analytics.html',
        total_correct=total_correct,
        total_incorrect=total_incorrect,
        total_picks=total_picks,
        win_percentage=win_percentage,
        sport_data=sport_data,
        prediction_log=prediction_log, # Pass log list to frontend template layout
        total_pushed=total_pushed
    )

@app.route('/help')
def help_page():
    # Publicly accessible route - renders documentation for all users
    return render_template('help.html')

if __name__ == '__main__':
    init_db()
    # host='0.0.0.0' opens the application up to the local network/Wi-Fi interface
    # port=5000 is the port address visitors will append to the host IP address
    app.run(host='0.0.0.0', port=5000, debug=True)
