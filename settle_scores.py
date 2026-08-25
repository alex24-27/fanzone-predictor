import sqlite3
import requests

DB_FILE = 'database.db'
LEAGUE_IDS = ['4346', '4429', '4391', '4479', '4387', '4607', '4424', '4380']

def settle_matches():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("Downloading recent sports results...")
    
    for league_id in LEAGUE_IDS:
        # Retrieve the most recent completed fixtures for each specific league
        url = f"https://www.thesportsdb.com/api/v1/json/4782693249/eventspastleague.php?id={league_id}"
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if not data or 'events' not in data or data['events'] is None:
                continue
                
            for event in data['events']:
                home_team = event['strHomeTeam']
                away_team = event['strAwayTeam']
                home_score = event.get('intHomeScore')
                away_score = event.get('intAwayScore')
                event_date = event.get('dateEvent') # API returns format: YYYY-MM-DD
                
                # Verify scores exist before executing evaluations
                if home_score is None or away_score is None:
                    continue
                    
                home_score = int(home_score)
                away_score = int(away_score)
                
                # Determine game winning entity
                if home_score > away_score:
                    winning_team = home_team
                elif away_score > home_score:
                    winning_team = away_team
                else:
                    winning_team = "Draw"
                
                # Find matching active records in the local system
                # Match teams, status, AND the specific calendar date.
                # SQLite's date() function strips the time out of the ISO "YYYY-MM-DDTHH:MM:SSZ" string.
                cursor.execute('''
                    SELECT id FROM games 
                    WHERE home_team = ? 
                      AND away_team = ? 
                      AND status = 'SCHEDULED'
                      AND date(game_date) = date(?)
                ''', (home_team, away_team, event_date))
                game = cursor.fetchone()
                
                if game:
                    game_id = game['id']
                    print(f"Settling Game ID {game_id}: {home_team} vs {away_team} -> Winner: {winning_team} ({home_score}-{away_score})")
                    
                    # Archive the matchup as closed
                    cursor.execute('''
                        UPDATE games 
                        SET status = 'FT', outcome = ?, home_score = ?, away_score = ? 
                        WHERE id = ?
                    ''', (winning_team, home_score, away_score, game_id))
                    
                    # Query all users who placed correct bets on this match
                    cursor.execute('''
                        SELECT user_id FROM predictions 
                        WHERE game_id = ? AND predicted_winner = ?
                    ''', (game_id, winning_team))
                    winning_predictions = cursor.fetchall()
                    
                    # Disburse points instantly to successful players
                    for pred in winning_predictions:
                        cursor.execute('''
                            UPDATE users 
                            SET score = score + 10 
                            WHERE id = ?
                        ''', (pred['user_id'],))
                        
            conn.commit()
        except Exception as e:
            print(f"Error handling score updates for League ID {league_id}: {e}")
            
    conn.close()
    print("Score calculation round complete.")

if __name__ == '__main__':
    settle_matches()
