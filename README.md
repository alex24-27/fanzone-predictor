# FanZone Predictor - Full-Stack Sports Predictor Application
A secure, responsive full-stack web application designed for logging, tracking, and managing sports predictions across multiple professional and collegiate leagues. This project demonstrates clean architecture patterns, robust server-side security mapping, asynchronous client-side validation, and background data automation.
## Key Engineering Features
- Asynchronous UX Updates (Fetch API): Replaced classic page reloads with non-blocking AJAX background submissions. Captures user prediction data seamlessly, updates interface button elements, and flashes a green highlight frame around target match containers without shifting browser scroll contexts.
- Dual-Layer Modification Safeguards: Implemented strict deadline constraints. If a match kickoff timestamp has passed, the frontend injects static badges to lock the option. Simultaneously, the backend routes independently query timestamps to block malicious post-kickoff writes, returning a `403 Forbidden` code if safety boundaries are breached.
- Dynamic Concurrency Limits (Max 5 Users Per Team): Features an automated pool liability firewall mimicking real-world sportsbook risk management. Enforces a maximum allocation ceiling of 5 users per team, dynamically displaying utilization bars, locking selections, and enabling complex user team-switching rules strictly through real-time server validations.
- Background Score Synchronization: Built decoupled, autonomous automated background scripts (`sync_data.py` and `settle_scores.py`) integrating with TheSportsDB API. The worker identifies concluded games in the database missing core metrics, reads JSON payloads, resolves scoring lines, identifies push/draw outcomes, and updates localized records safely.
- Live AJAX Registration Validation: Upgraded account onboarding with case-insensitive availability check lookups, running efficiently via an input debounce timer mechanics script (300ms) to prevent database transaction spamming.
- Data Isolation & Security: Replaced static structures with state-aware `flask.session` identifier objects. Mitigated SQL Injection vulnerabilities by enforcing query parameterization layers across all SQLite execution paths.
## Tools Used in Development
- Backend: Python with Flask
- Frontend: HTML with CSS
- Data Metrics Engine: Chart.js
- External Integration Source: TheSportsDB API
