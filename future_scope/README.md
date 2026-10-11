# Future scope: AI quiz generation from lecture slides

Removed from the app for now; kept here so it can be brought back.

`llm_quiz.py` (this folder) does the whole pipeline:
slide extraction (PDF/PPTX) -> topic grouping -> MCQ generation with Google Gemini
(free tier) -> validation, option shuffling and marks splitting.

To restore it:
1. Move `llm_quiz.py` back next to `app.py`.
2. `pip install python-pptx`, and put `GEMINI_API_KEY=<free key from https://aistudio.google.com/apikey>`
   (optionally `GEMINI_MODEL`) in `.env`.
3. Re-add a faculty "Quiz Generator" page in `app.py`. It needs: upload + `extract_slides` /
   `analyze_topics`, a topic picker, `generate_mcqs`, an editable review of the answer key,
   then `DataManager.create_exam(..., window_mins=...)` with `to_exam_questions(...)`.

Already in place and still used: the `materials` table and
`create_material` / `get_materials` / `delete_material` in `data_manager.py`.
The student-side score screen and MCQ auto-grading are part of the normal exam flow.
