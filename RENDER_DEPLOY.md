Render deployment guide

1. Create a new Web Service on Render:
   - Connect your GitHub repo and select the branch to deploy.
   - For Build Command: leave blank (Render will run pip install -r requirements.txt by default).
   - For Start Command: use `gunicorn viewer_app:app --bind 0.0.0.0:$PORT --workers 4` (Procfile will also be used).

2. Set environment variables in Render dashboard:
   - `FLASK_SECRET_KEY` (set to a secure value)
   - Any other env vars you need

3. Ensure the repo contains `requirements.txt` and `runtime.txt` (already present).

4. Optionally add a health check in the Render service pointing to `/health` (returns JSON). 

5. Deploy and monitor logs in Render dashboard; the app will be served by Gunicorn.

---

## Troubleshooting: build fails while installing dependencies (pandas compile errors)

If your Render build fails during `pip install -r requirements.txt` with errors compiling `pandas` (errors referencing `_PyLong_AsByteArray`, `meson`, `ninja`, or failing C compilation), this usually means Render selected Python 3.13 for the build and `pandas` in your `requirements.txt` needs a compatible wheel for that Python version.

Quick fixes:

- Pin the Python runtime to 3.11 by adding `runtime.txt` with a line like:

```
python-3.11.6
```

Then push the change and trigger a new deploy. Render will use Python 3.11 and pandas will install using pre-built wheels (no compilation).

- Alternatively, if you must use Python 3.13, upgrade to a pandas wheel that supports 3.13 (check pandas release notes) or prebuild wheels in CI, but the simplest and recommended option is to use Python 3.11 for now.

After making the change, re-deploy (push to your branch) and check the build logs. If Render still used Python 3.13 and attempted to build pandas from source, **clear the build cache and redeploy**:

1. In the Render dashboard, open your Service → Overview.
2. Click the **Manual Deploy** dropdown and select **Clear cache and deploy** (this forces Render to re-evaluate `runtime.txt`/`render.yaml`).
3. Monitor the build logs — it should now pick up Python 3.11 and install prebuilt pandas wheels.

If there are further errors, paste the new build output into the Render logs and I can help diagnose the next step.
