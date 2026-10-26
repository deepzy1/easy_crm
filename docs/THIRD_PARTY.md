# Direct dependency inventory

Recorded from installed package metadata and the pinned manifests on 26 October 2026. The EasyCRM project license is still unselected; third-party packages retain their own licenses. This inventory is not a claim that all transitive distribution obligations have been reviewed.

Runtime Python dependencies:

- FastAPI 0.162.0 — MIT.
- Starlette 1.10.0 — BSD-3-Clause; pinned explicitly to include current security fixes.
- SQLAlchemy 2.0.41 and Alembic 1.16.2 — MIT.
- psycopg / psycopg-binary 3.2.9 — LGPLv3. Binary distributions also include libraries with their own notices; preserve their distribution license files.
- Pydantic 2.11.7, pydantic-settings 2.10.1, email-validator 2.2.0 — MIT.
- pwdlib 0.2.1 and argon2-cffi 23.1.0 — MIT.
- Uvicorn 0.34.3 and httpx 0.28.1 — BSD-3-Clause.

Frontend direct runtime dependencies:

- React / React DOM 19.1.0 — MIT.
- TanStack React Query 5.81.2 — MIT.
- Lucide React 0.515.0 — ISC.

Tooling includes Vite, TypeScript, Tailwind CSS, Prettier, pytest, Ruff, and Playwright; their package license files remain in installed distributions. Exact direct frontend versions are in `frontend/package.json`; complete versions are locked in `package-lock.json`. Python runtime/dev trees are locked with hashes in `backend/requirements.lock` and `requirements-dev.lock`.

No Attio assets, logo, or proprietary UI code were copied. The supplied dashboard image was used only as a design reference. The EasyCRM mark is an original CSS treatment. Fonts are loaded through Google Fonts (DM Sans and Manrope); no font binary is vendored. Provider services, model weights, API terms, and container base images have their own terms and are separate from application dependency licensing.
