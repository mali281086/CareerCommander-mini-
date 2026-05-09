import re
import json

# Replicating the logic from job_hunter/analysis_crew.py for verification
def _clean_json(text):
    if not text or not isinstance(text, str):
        return {}

    def try_parse(json_str):
        try:
            # Cleanup trailing commas in objects and arrays before parsing
            json_str = re.sub(r",\s*\}", "}", json_str)
            json_str = re.sub(r",\s*\]", "]", json_str)
            data = json.loads(json_str)
            if isinstance(data, dict):
                return data
        except:
            pass
        return None

    best_data = {}

    try:
        # 1. Try finding Markdown code blocks
        matches = re.findall(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        for inner_text in matches:
            data = try_parse(inner_text.strip())
            if data and len(data) > len(best_data):
                best_data = data

        if best_data and len(best_data) >= 3:
            return best_data

        # 2. String-aware brace counting
        starts = [i for i, char in enumerate(text) if char == '{']
        for start in starts:
            count = 0
            in_string = False
            escape = False
            for i in range(start, len(text)):
                c = text[i]
                if escape:
                    escape = False
                    continue
                if c == '\\':
                    escape = True
                    continue
                if c == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if c == '{': count += 1
                    elif c == '}': count -= 1
                    if count == 0:
                        potential_json = text[start:i+1]
                        data = try_parse(potential_json)
                        if data and len(data) > len(best_data):
                            best_data = data
                        break
        return best_data
    except Exception as e:
        return {"error": str(e)}

# TEST CASES
def run_tests():
    # Case 1: The Reported Bug (Nested objects)
    bug_text = """{
  "company_intel": {
    "mission": "To test",
    "key_facts": ["fact1"]
  },
  "ats_report": {
    "score": 85,
    "missing_skills": ["skill1"]
  },
  "status": "success"
}"""
    result = _clean_json(bug_text)
    print(f"Test 1 (Root Extraction): {'PASS' if 'status' in result and 'company_intel' in result else 'FAIL'}")

    # Case 2: Markdown with trailing commas
    md_text = """
Some intro text.
```json
{
  "test": "value",
  "list": [1, 2, ],
}
```
"""
    result = _clean_json(md_text)
    print(f"Test 2 (Markdown + Trailing Comma): {'PASS' if result.get('test') == 'value' else 'FAIL'}")

    # Case 3: Multiple objects, pick the largest
    multi_text = """
{ "small": 1 }
{ "larger": 2, "than": "small", "status": "ok" }
"""
    result = _clean_json(multi_text)
    print(f"Test 3 (Largest Object): {'PASS' if 'larger' in result else 'FAIL'}")

    # Case 4: Escaped Quotes
    # Using raw string for the input text to simulate what actually comes from the browser/LLM
    text4 = r"""
{
  "content": "This is a \"quote\" inside",
  "status": "success"
}
"""
    result4 = _clean_json(text4)
    print(f"Test 4 (Escaped Quotes): {'PASS' if result4.get('content') == 'This is a \"quote\" inside' else 'FAIL'}")
    if result4.get('content') != 'This is a \"quote\" inside':
        print(f"  Expected: This is a \"quote\" inside")
        print(f"  Got:      {result4.get('content')}")

if __name__ == "__main__":
    run_tests()
