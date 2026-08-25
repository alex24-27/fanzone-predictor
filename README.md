# FanZone Predictor - Full-Stack Sports Predictor Application
A secure, responsive full-stack web application designed for logging, tracking, and managing sports predictions across multiple professional and collegiate leagues. This project demonstrates clean architecture patterns, robust server-side security mapping, asynchronous client-side validation, and background data automation.
## Key Engineering Features
- Asynchronous UX Updates (Fetch API): Replaced classic page reloads with non-blocking AJAX background submissions. Captures user prediction data seamlessly, updates interface button elements, and flashes a green highlight frame around target match containers without shifting browser scroll contexts.
- Dual-Layer Modification Safeguards: Implemented strict deadline constraints. If a match kickoff timestamp has passed, the frontend injects static badges to lock the option. Simultaneously, the backend routes independently query timestamps to block malicious post-kickoff writes, returning a `403 Forbidden` code if safety boundaries are breached.
- Dynamic Concurrency Limits (Max 5 Users Per Team): Features an automated pool liability firewall mimicking real-world sportsbook risk management. Enforces a maximum allocation ceiling of 5 users per team, dynamically displaying utilization bars, locking selections, and enabling complex user team-switching rules strictly through real-time server validations.
- Background Score Synchronization: Built decoupled, autonomous automated background scripts (`sync_data.py` and `settle_scores.py`) integrating with TheSportsDB API. The worker identifies concluded games in the database, reads JSON payloads, resolves scoring lines, identifies push/draw outcomes, and updates localized records safely.
- Live AJAX Registration Validation: Upgraded account onboarding with case-insensitive availability check lookups, running efficiently via an input debounce timer mechanics script (300ms) to prevent database transaction spamming.
- Data Isolation & Security: Replaced static structures with state-aware `flask.session` identifier objects. Mitigated SQL Injection vulnerabilities by enforcing query parameterization layers across all SQLite execution paths.
## Technology Stack
- Backend: Python with Flask
- Frontend: HTML with CSS
- Data Metrics Engine: Chart.js
- External Integration Source: TheSportsDB API (https://www.thesportsdb.com/documentation)
## Setup and Installation
First, ensure you have Python 3.8+ and Git successfully installed on your computer. Then,
1. Open a terminal or command prompt.
2. Navigate to the folder where you want to save the project.
3. Run the following command to clone the repository:
    ```bash
    git clone <repository-url>
    ```
    Replace `<repository-url>` with the actual URL of the repository.
4. Navigate into the cloned folder:
    ```bash
    cd fanzone-predictor
    ```
## Environment Setup
1. Open a terminal or command prompt.
2. Run the following command to create the environment directory:
    ```bash
    python -m venv venv
    ```
3. Run one of the following commands based on your operating system to activate the virtual environment:
   | Command | Operating System |
   |---------|------------------|
   | `source venv/bin/activate` | macOS/Linux |
   | `venv\Scripts\activate` | Windows (Command Prompt) |
   | `.\venv\Scripts\Activate.ps1` | Windows (PowerShell) |
## Installing Dependencies
Create a text document named `requirements.txt` inside the root directory of the project containing the following packages, then execute the installation command:
```
blinker==1.9.0
certifi==2026.5.20
charset-normalizer==3.4.7
click==8.4.1
colorama==0.4.6
Flask==3.1.3
idna==3.18
itsdangerous==2.2.0
Jinja2==3.1.6
MarkupSafe==3.0.3
requests==2.34.2
urllib3==2.7.0
Werkzeug==3.1.8
```

```bash
python -m pip install -r requirements.txt
```
## Running the Project
```bash
python app.py
```
This will start the development server, typically located at `http://127.0.0.1:5000`. If the database file does not exist, one will be created automatically when the application is executed.
To pull upcoming events using the external API and settle concluded events, run the following scripts:
```bash
python sync_data.py
```
```bash
python settle_scores.py
```
