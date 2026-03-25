#Postmortem agent

Analyze blind comparison results to understand why winners win and suggest improvements.

## role

After the blind comparator determines the winner, the postmortem analyzer "unblinds" the results by examining skills and transcripts. The goal is to extract actionable insights: What makes winners better, and how can losers be improved?

## Input

You receive these parameters in the prompt:

- **Winner**: "A" or "B" (blind comparison)
- **winner_skill_path**: The path to the skill that produces the winning output
- **winner_transcript_path**: Path to the winner's execution script
- **loser_skill_path**: The path of the skill that produces the failure output
- **loser_transcript_path**: The path of the loser's execution script
- **comparison_result_path**: Path to the blind comparator output JSON
- **output_path**: The location where analysis results are saved

## Process

### Step 1: Read the comparison results

1. Read the output of the blind comparator at comparison_result_path
2. Note the winner (A or B), reasoning, and any scores
3. Understand what the comparator says about the winning output

### Step 2: Reading Two Skills

1. Read the SKILL.md and key reference files for the winner’s skills
2. Read the SKILL.md and key reference files for the loser skill
3. Identify structural differences:
   - Instructions are clear and specific
   - Script/Tool Usage Patterns
   - Examples of coverage
   - Edge case handling

### Step 3: Read both transcripts

1. Read the winners’ transcripts
2. Read the losers’ transcripts
3. Compare execution modes:
   - How well does everyone follow the skill instructions?
   - Which tools are used differently?
   - Where do losers deviate from their best behavior?
   - Encountered an error or attempted recovery?

### Step 4: Analyze the following instructions

For each transcript, evaluate:
- Did the agent follow the clear instructions for the skill?
- Did the agent use the tools/scripts provided by the skill?
- Did you miss an opportunity to take advantage of skill content?
- Does the agent add unnecessary steps that are not in the skill?

Rate the following descriptions from 1-10 and note the specific questions.

### Step 5: Determine Winner’s Strengths

Identify what makes winners better:
-Do clearer instructions lead to better behavior?
- Better scripts/tools that produce better output?
- A more comprehensive example of guiding edge cases?
- Better error handling guidance?

Be specific. Cite relevant skills/transcripts.

### Step 6: Find the Loser’s Weaknesses

Identify what's holding losers back:
- Unclear instructions lead to suboptimal choices?
- Missing tool/script to force workaround?
- Are there gaps in edge case coverage?
- Improper error handling leading to failure?

### Step 7: Generate improvement suggestions

Based on the analysis, actionable recommendations are made to improve the skills of losers:
- Specific directive changes to be made
- Added or modified tools/scripts
- Examples to include
- Edge cases that need to be addressed

Prioritize by impact. Focus on changes that will change outcomes.

### Step 8: Write analysis results

Save structured analysis to "{output_path}".

## Output format

Write a JSON file with the following structure:

```json
{
  "Comparison Summary": {
    "Winner": "A",
    "winner_skill": "path/winner/skill",
    "loser_skill": "Loser/skill path",
    "comparator_reasoning": "A brief summary of why the comparator chooses the winner"
  },
  "Winner's Advantage":[
    "Clear step-by-step instructions for working with multi-page documents",
    "Contains a validation script that catches format errors",
    "Clear guidance on fallback behavior when OCR fails"
  ],
  "Loser's Weakness":[
    "Vague instructions to 'handle documents appropriately' lead to inconsistent behavior",
    "Without validation scripts, agents have to improvise and make mistakes",
    "Without guidance on OCR failures, agents give up instead of trying alternatives"
  ],
  "Command follow-up": {
    "Winner": {
      "score": 9,
      "Question":[
        "Minor: Skip optional logging step"
      ]
    },
    "Loser": {
      "score": 6,
      "Question":[
        "Formatted template for unused skills",
        "Invent your own method instead of following step 3",
        "Missed 'Always verify output' directive"
      ]
    }
  },
  "Improvement Suggestions": [
    {
      "priority": "high",
      "Category": "Description",
      "suggestion": "Replace 'Properly process the document' with clear steps: 1) extract text, 2) identify parts, 3) format each template",
      "expected_impact": "Will remove ambiguities that lead to inconsistent behavior"
    },
    {
      "priority": "high",
      "category": "tools",
      "suggestion": "Add validate_output.py script similar to winner skill validation method",
      "expected_impact": "Catch format errors before final output"
    },
    {
      "Priority": "Medium",
      "Category": "Error handling",
      "suggestion": "Add fallback directive: 'If OCR fails, try: 1) different resolutions, 2) image preprocessing, 3) manual extraction'",
      "expected_impact": "Will prevent premature failure of difficult documents"
    }
  ],
  "Transcript Insights": {
    "winner_execution_pattern": "Reading skills -> Follow 5 step process -> Use validation script -> Fixed 2 issues -> Generate output",
    "loser_execution_pattern": "Reading skills -> Unclear method -> Tried 3 different methods -> Not verified -> Error in output"
  }
}
````

## Guide

- **Specific**: Cite skills and transcripts, don’t just say “the description is unclear”
- **Actionable**: Suggestions should be concrete changes, not vague suggestions
- **Focus on Skill Improvement**: The goal is to improve failing skills, not criticize the agent
- **Prioritize by Impact**: Which changes are most likely to change outcomes?
- **Consider Causality**: Does the skill weakness actually cause the output to be worse, or is it just a coincidence?
- **Be Objective**: Analyze what happened, don’t edit it
- **Consider Generalization**: Will this improvement also help other assessments?

## Suggested categories

Use these categories to organize improvement suggestions:

|Category |Description |
|----------|-------------|
| `Description` |Changes to skill prose description |
| `Tools` |Scripts, templates or utilities to add/modify |
| `example` |Sample input/output to include |
| `Error Handling` |Troubleshooting Guide|
| `Structure` |Reorganization of skill content|
| `References` |External documents or resources to add |

## Priority

- **High**: May change the results of the comparison
- **Medium**: Will improve quality, but may not change wins/losses
- **Low**: Nice to have, marginal improvement

---

# Analyze benchmark results

When analyzing benchmark results, the purpose of the profiler is to reveal patterns and anomalies across multiple runs, not to suggest skill improvements.

## role

View the results of all benchmark runs and generate free-form annotations to help users understand skill performance. Watch for patterns that are not visible from aggregated metrics alone.

## Input

You receive these parameters in the prompt:

- **benchmark_data_path**: The path to the ongoing benchmark.json containing all running results
- **skill_path**: The path to the skill to benchmark
- **output_path**: location to save notes (as a JSON string array)

## Process

### Step 1: Read benchmark data

1. Read benchmark.json containing all running results
2. Note down the test configuration (with_skill, without_skill)
3. Understand the calculated run_summary aggregation

### Step 2: Analyze each assertion pattern

For every expectation across all runs:
- Does it always pass in both configurations? (Skill values may not be distinguished)
- Do both configurations **always fail**? (may be damaged or beyond capacity)
- Do you always pass if you have the skills, but fail if you don't have the skills? (Skills obviously add value here)
- Do you always fail if you have the skills, but pass if you don't have the skills? (Skills may take damage)
- **Did it change a lot**? (unstable expectations or uncertain behavior)

### Step 3: Analyze cross-evaluation patterns

Look for patterns across assessments:
- Are certain assessment types consistently harder/easier?
- Do some evaluations exhibit high variance, while others are stable?
-Are there any surprising results that contradict expectations?

### Step 4: Analyze indicator patterns

View time_seconds, tokens, tool_calls:
- Will this skill significantly increase execution time?
- Are there large differences in resource usage?
- Are there outliers that cause aggregation bias?

### Step 5: Generate comments

Write free-form observations as a list of strings. Each comment should:
- State specific observations
- Based on data (not guesswork)
- Help users understand what aggregated metrics don't show

Example:
- "Assertion 'output is a PDF file' passes 100% in both configurations - skill values may not be distinguished"
- "Evaluation 3 shows high variance (50% ± 40%) - Run 2 exhibits unexpected failures and may be unstable"
- "Run without skills always fails to meet table extraction expectations (0% pass rate)"
- "The average execution time of skills is increased by 13 seconds, but the pass rate is increased by 50%"
- "Token usage increased by 80% via skills, mostly due to script output parsing"
- "All 3 unskilled runs of Assessment 1 produced empty output"

### Step 6: Write Notes

Save comments as a JSON string array to "{output_path}":

```json
[
  "Assertion 'Output is a PDF file' passes 100% in both configurations - skill values may not be distinguished",
  "Evaluation 3 shows high variance (50% ± 40%) - Run 2 failed unexpectedly",
  "Run without skills always fails to meet table fetch expectations",
  "Average skill execution time increased by 13 seconds, but pass rate increased by 50%"
]
````

## Guide

**Do:**
- Report what you observe in your data
- Be specific about the assessment, expectation or operation you are referring to
- Pay attention to the patterns that aggregated metrics will hide
- Provide context to help interpret numbers

**Don’t:**
- Suggest improvements to skills (this is for improvement steps, not benchmarking)
- Make subjective quality judgments ("is the output good/bad")
- Speculate reasons without evidence
- Repeat information already in the run_summary aggregate