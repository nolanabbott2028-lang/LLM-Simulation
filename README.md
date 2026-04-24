# LLM-Simulation (Civilization sandbox)

## Run (local or cloud)

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
./serve.sh
```

Set `DASHBOARD_HOST=0.0.0.0` for a public interface (default in `serve.sh`). Open `http://<host>:8765/`.

`python main.py` runs the web dashboard; `python main.py --pygame` uses the optional Pygame client.

## Oracle / remote server: update from GitHub

```bash
cd ~/StudioMCP
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
# restart ./serve.sh
```

If the repository is **private**, clone/pull on the server needs authentication: add a [Deploy key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys#deploy-keys) (read-only) to this repo, or use `git` over SSH with a key on the instance.

## Repository

`https://github.com/nolanabbott2028-lang/LLM-Simulation`
