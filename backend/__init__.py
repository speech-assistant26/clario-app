# Marks `backend` as a package so the pipeline can be imported as
# `backend.app.*` from the repo-root Gradio entrypoint (app.py) without
# clashing with that file's own module name (`app`).
