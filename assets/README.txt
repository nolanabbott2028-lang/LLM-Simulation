map.png
  Overworld / terrain image, scaled to the world size. Replace with your own art.

sims/idle.png
  Standing / front view — used when the sim is still on land.

sims/walk.png
  Side (profile) view — used while moving on land; mirrored when facing left.

sims/swim.png
  Rear / three-quarter back view — used in water (lakes, rivers, sea on the map).

PNG transparency is supported. To pull the local LLM used by the game, from the project root run:
  python3 setup_ollama.py
Start the Ollama app, or in a shell run:  ollama serve
(Do not paste whole instruction blocks into the shell — lines starting with # are not commands.)
