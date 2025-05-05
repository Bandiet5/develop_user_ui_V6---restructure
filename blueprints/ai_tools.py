import pandas as pd
import os
import time
import re


# 📄 Load Excel files
def read_excel_files(file1, file2=None):
    dfs = []
    for file in [file1, file2]:
        if file:
            try:
                df = pd.read_excel(file)
                print(f"[READ EXCEL] Loaded {file.filename} with {df.shape[0]} rows, {df.shape[1]} columns.")
                dfs.append(df)
            except Exception as e:
                print(f"[READ EXCEL ERROR] Could not read {file.filename}: {e}")
    return dfs

# 🧠 Generate Python code from user question
def summarize_data(df1, df2=None, question="", table_names=None):
    start = time.time()

    from gpt4all import GPT4All

    # ✅ Config for model
    MODEL_NAME = "mistral-7b-instruct-v0.1.Q4_0.gguf"
    MODEL_DIR = "C:/Users/Pieter/.cache/gpt4all"

    print("🤖 Loading model...")
    model = GPT4All(
        model_name=MODEL_NAME,
        model_path=MODEL_DIR,
        allow_download=False,  # Manual download
        n_threads=8
    )
    print("✅ Model ready.")



    prompt = f"""
You are a Python pandas assistant. The user asked: "{question}"

You have access to the following pandas DataFrames:
- df1: main dataset
- df2: optional second dataset (may be None)

{f"Table names: {', '.join(table_names)}" if table_names else ""}

Your task:
- Write valid Python pandas code to answer the question.
- Assign your final answer to a variable named 'result'.
- ONLY output a single line or block of executable Python code.
- DO NOT explain anything.
- DO NOT output markdown, text, or comments.
- DO NOT use print(), display(), or show().
- The code MUST start with: result =
- To select multiple columns, always use double square brackets: df[["col1", "col2"]]


Examples:
result = df1.head(3)
result = df1[df1['status'] == 'active']
result = df1.sort_values('date')
Q: show first 3 rows → result = df1.head(3)
Q: filter where df1['status'] is 'active' → result = df1[df1['status'] == 'active']
Q: select name and age → result = df1[["name", "age"]]

⚠️ IMPORTANT: Only return clean Python code starting with 'result ='. No text, no formatting.

BEGIN CODE:
"""

    # 👇 No more big data previews (makes prompt smaller and faster)
    # You can comment out the next two lines if needed
    # prompt += "\n\n### df1 preview:\n" + df1.head(3).to_string(index=False)
    # if df2 is not None:
    #     prompt += "\n\n### df2 preview:\n" + df2.head(3).to_string(index=False)

    print("🧠 Prompt sent to AI:\n" + "="*40)
    print(prompt)

    response = model.generate(prompt, max_tokens=250).strip()
    response = response.replace('\u00A0', ' ').strip()  # Replace non-breaking spaces if needed

    print("\n🧠 AI Response:\n" + "="*40)
    print(response)

    # ✅ Only accept response that starts with "result ="
    if not response.lower().startswith("result"):
        raise ValueError("❌ AI did not return valid code.")

    print(f"✅ AI done in {time.time() - start:.2f} seconds.")
    return response



# 🧪 Execute generated code
def run_generated_code(df1, df2, code):
    local_vars = {'df1': df1, 'df2': df2}
    result_html = ""
    result_df = None

    try:
        print("\n🧪 Executing AI Code:\n" + "="*40)
        print(code)

        # Clean up code
        cleaned_code = re.sub(r'\b0+(\d+)\b', r'\1', code)  # remove leading 0s
        cleaned_code = cleaned_code.replace('\u00A0', ' ')  # clean spaces
        cleaned_code = re.sub(r'[^\x00-\x7F]+', ' ', cleaned_code)  # ASCII only (safety)

        # Run
        exec(cleaned_code, {}, local_vars)
        result = local_vars.get("result")

        # Show result
        if isinstance(result, pd.DataFrame):
            result_df = result
            print(f"[RESULT] DataFrame shape: {result.shape}")
            result_html = result.to_html(classes="ai-output-table", index=False, border=1)
        else:
            print(f"[RESULT] Non-DataFrame: {type(result)}")
            result_html = f"<pre>{str(result)}</pre>"

    except Exception as e:
        print(f"[ERROR] Code execution failed: {e}")
        result_html = f"<div style='color:red;'>❌ Error while executing code:<br>{str(e)}</div>"

    return result_html, result_df, code
