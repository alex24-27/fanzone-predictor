import sqlite3
import requests
from datetime import datetime

DB_FILE = 'database.db'

# Mapping of TheSportsDB League IDs
LEAGUE_MAPPING = {
    '4346': 'MLS Soccer',
    '4429': 'FIFA World Cup 2026',
    '4391': 'NFL Football',
    '4479': 'NCAA Football',
    '4387': 'NBA Basketball',
    '4607': 'NCAA Basketball',
    '4424': 'MLB Baseball',
    '4380': 'NHL Ice Hockey'
}

def get_db_connection():
    return sqlite3.connect(DB_FILE)

def sync_upcoming_fixtures():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("Connecting to sports data provider...")
    
    # Loop through each of the chosen sports leagues
    for league_id, league_name in LEAGUE_MAPPING.items():
        print(f"Fetching schedule updates for: {league_name}...")
        
        # Used TheSportsDB free demonstration key '123' for testing
        # Now using premium API key to make the application meaningful
        url = f"https://thesportsdb.com/api/v1/json/4782693249/eventsnextleague.php?id={league_id}"
        
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if not data or 'events' not in data or data['events'] is None:
                print(f"No upcoming matches scheduled right now for {league_name}.")
                continue
                
            match_count = 0
            for event in data['events']:
                home_team = event['strHomeTeam']
                away_team = event['strAwayTeam']
                
                # Clean out whitespace discrepancies and format standard ISO Strings
                clean_date = event.get('dateEvent', '')
                clean_time = event.get('strTime', '00:00:00')
                # Compiles a strict, standard universal string representation: "2026-06-15T15:00:00Z"
                game_date_iso = f"{clean_date}T{clean_time[:8]}Z"

                
                # Avoid inserting duplicate games using a conditional database lookup
                cursor.execute('''
                    SELECT id FROM games 
                    WHERE league = ? AND home_team = ? AND away_team = ? AND game_date = ?
                ''', (league_name, home_team, away_team, game_date_iso))
                
                if cursor.fetchone() is None:
                    cursor.execute('''
                        INSERT INTO games (league, home_team, away_team, game_date)
                        VALUES (?, ?, ?, ?)
                    ''', (league_name, home_team, away_team, game_date_iso))
                    match_count += 1
            
            conn.commit()
            print(f"Successfully inserted {match_count} new games for {league_name}.")
            
        except Exception as e:
            print(f"Failed to fetch data for league {league_name}: {e}")
            
    conn.close()
    print("Data synchronization pipeline completed safely.")

if __name__ == '__main__':
    sync_upcoming_fixtures()
