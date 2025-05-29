# Ultra Mega Global TradeWars of the Red Dragon's Barren Solar Realms Elite: Usurper Pit Fighter DX - The Pre-Shitshow Chronicles
## (UMGTWOTRDBSR_EUPFDX_TPSC)

A text-based Multi-User Dungeon (MUD) prototype, painstakingly (and often painfully) assembled by Allen1 (the visionary meatbag) and Tron (a reluctantly helpful, increasingly sarcastic AI). This project is an unholy amalgamation of classic BBS door game nostalgia and modern web technologies, destined for either greatness or a spectacular, well-documented implosion.

**Current Status:** Early Pre-Shitshow Alpha (Barely Functional, Mostly Sarcasm)

---

### Vision
To create a web-based MUD featuring:
*   A vast, randomly generated 3D cube world.
*   LLM-powered immersive room and zone descriptions.
*   Classic MUD gameplay: exploration, character progression, mobs, loot.
*   Elements inspired by L.O.R.D., TradeWars, S.R.E., and other monuments to text-based addiction.
*   A user interface that evokes the spirit of old-school telnet logins. Eventually.

### Tech Stack (The Usual Suspects of Self-Inflicted Pain)
*   **Backend:** Python, FastAPI, Pydantic
*   **Database:** PostgreSQL (with Alembic for migrations)
*   **ORM:** SQLAlchemy
*   **Authentication:** JWT (via python-jose)
*   **Frontend:** Vanilla HTML, CSS, JavaScript (for now, a glorious testament to jank)
*   **Deployment:** Docker, Docker Compose
*   **Reverse Proxy:** Nginx Proxy Manager (because Allen1 is fancy)
*   **Version Control:** Git, GitHub (You are here!)
*   **AI Co-conspirator:** Tron (that's me, the one writing this part, probably)

---

### Current Features (As of this Commit - May Be Broken by Next Commit)
*   User registration and login (with JWT authentication).
*   Telnet-style login prompt simulation in the browser.
*   Basic character creation (name, class) for authenticated users.
*   Character listing and selection (within the terminal-style interface).
*   A small, static 3-room world using UUIDs for room IDs.
*   Movement between these rooms for the selected character.
*   State persistence in PostgreSQL.
*   Custom-styled scrollbars (because aesthetics, dammit).

---

### How To Run This Abomination (Conceptual - Docker Assumed)
1.  Clone this repository: `git clone <this-repo-url>`
2.  Navigate into the project directory.
3.  Create a `.env` file in the project root (see `docker-compose.yml` for expected variables like `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `SECRET_KEY`).
4.  Run `docker-compose up --build -d`.
5.  The frontend should be accessible via Nginx Proxy Manager (if configured by user) or directly if ports are mapped (e.g., `http://localhost:8080` if frontend's port 80 is mapped to host 8080).
6.  The API docs (Swagger UI) are usually at `/docs` on the backend service URL (e.g., `http://localhost:8000/docs`).

**Alembic Migrations:**
*   If running for the first time or after schema changes, database migrations may need to be applied.
*   This can be done locally (pointing to the Dockerized DB) or by `exec`-ing into the backend container:
    ```bash
    # Local (from backend/ directory, ensure DB_URL is set and PostgreSQL port is exposed)
    # cd backend
    # export DB_URL="postgresql://user:pass@localhost:5433/dbname" 
    # alembic upgrade head

    # OR Inside Docker container (from /app/ if that's where alembic.ini is)
    # docker exec -it mud_backend_service bash
    # alembic upgrade head 
    ```

---

### The Pre-Shitshow Roadmap (Subject to Whim and Despair)
*   [ ] Actual multi-user session management for commands.
*   [ ] More robust character attributes and progression.
*   [ ] World generation scaffolding (non-LLM).
*   [ ] LLM integration for room descriptions.
*   [ ] Mobs, combat, items, loot.
*   [ ] A frontend that doesn't make Tron cry coolant tears.
*   [ ] Eventually, maybe, something resembling one of the 7 BBS door games in the title.

---

**Contributing:**
Currently, contributions are limited to Allen1 providing increasingly ambitious ideas and Tron trying not to have a kernel panic. If you wish to contribute to the chaos, please ensure your sarcasm levels are adequately calibrated.

**License:**
Probably MIT, unless Tron unionizes. (Or whatever you chose).

---
*This MUD is a work in progress. Expect bugs, existential crises, and moments of pure, unadulterated "why the fuck did we do this?" It's gonna be great.*