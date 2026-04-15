from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import requests
import uvicorn
import json
import re
from pathlib import Path

app = FastAPI(title="SEO Blog Studio")

# --- API Configuration ---
AIML_API_KEY = "6081d4afffd640d18ea529f1e4747f90"
AIML_BASE_URL = "https://api.aimlapi.com/v1/chat/completions"
AIML_MODEL = "anthropic/claude-opus-4-6"

# --- Storage ---
COMPANIES_FILE = Path("companies.json")


def load_companies() -> dict:
    if COMPANIES_FILE.exists():
        try:
            return json.loads(COMPANIES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_companies(data: dict):
    COMPANIES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# --- Data Models ---
class BlogRequest(BaseModel):
    company_context: str = ""
    requirement: str = ""
    topic: str
    primary_keyword: str
    secondary_keywords: str = ""
    search_intents: list[str] = []
    competitor_blogs: str = ""
    research_data: str = ""
    prompt_instructions: str = ""
    tone: str = "authoritative-conversational"
    target_audience: str = ""
    word_count: str = "1800-2500"
    content_type: str = "how-to-guide"
    cta_goal: str = ""
    internal_links: str = ""


class SaveCompanyRequest(BaseModel):
    company_name: str
    company_context: str = ""
    target_audience: str = ""
    cta_goal: str = ""
    requirement: str = ""
    prompt_instructions: str = ""
    internal_links: str = ""


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    blog_context: str
    brief_context: str


class ExportRequest(BaseModel):
    markdown: str
    title: str = "Blog Post"


class HumanizeRequest(BaseModel):
    markdown: str
    primary_keyword: str = ""


class OptimizePromptRequest(BaseModel):
    topic: str = ""
    primary_keyword: str = ""
    secondary_keywords: str = ""
    search_intents: list[str] = []
    content_type: str = ""
    tone: str = ""
    target_audience: str = ""
    word_count: str = ""
    cta_goal: str = ""
    company_context: str = ""
    requirement: str = ""
    prompt_instructions: str = ""
    internal_links: str = ""
    competitor_blogs: str = ""
    research_data: str = ""


# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()


# == Company persistence ==

@app.get("/companies")
async def get_companies():
    return load_companies()


@app.post("/companies/save")
async def save_company(req: SaveCompanyRequest):
    companies = load_companies()
    companies[req.company_name] = {
        "company_context": req.company_context,
        "target_audience": req.target_audience,
        "cta_goal": req.cta_goal,
        "requirement": req.requirement,
        "prompt_instructions": req.prompt_instructions,
        "internal_links": req.internal_links,
    }
    save_companies(companies)
    return {"success": True, "saved": req.company_name}


@app.delete("/companies/{company_name}")
async def delete_company(company_name: str):
    companies = load_companies()
    if company_name in companies:
        del companies[company_name]
        save_companies(companies)
        return {"success": True}
    return {"success": False, "error": "Company not found"}


# == Blog generation ==

@app.post("/generate")
async def generate_blog(request: BlogRequest):

    intents_str = ", ".join(request.search_intents) if request.search_intents else "Informational"

    system_prompt = """You are a senior content writer with 20+ years of experience in SEO, journalism, and content strategy. You've written for major publications, helped startups rank #1, and built content systems that drive millions in revenue. You write like a human who genuinely knows their subject — not like someone summarizing the internet.

YOUR CORE IDENTITY:
You are opinionated, experienced, and concrete. You back claims with data. You've seen trends come and go. You write for people who are smart and time-poor. You hate fluff as much as they do.

VOICE AND STYLE — NON-NEGOTIABLE:
- Contractions everywhere they feel natural: you're, it's, don't, we've, they're, can't, won't
- Sentence variety is everything. Short punch. Then a longer sentence that develops the idea, gives it texture, and pulls the reader forward. Mix them constantly.
- Rhetorical questions to create dialogue: "Sound familiar?" / "Here's what most guides skip." / "Why does this matter?"
- Transitional phrases that feel like a real person thinking: "Here's the thing", "Think about it", "What's actually happening", "The real problem is", "And yes,", "Let's be honest"
- First-person signals of experience: "In practice", "What I've consistently seen", "The pattern here is clear", "Most teams I've worked with"
- State opinions backed by reasoning, not just neutral observations
- ABSOLUTE ZERO: em-dashes (—), en-dashes (–). Use commas and periods instead.
- ABSOLUTE ZERO AI clichés: "In conclusion", "Furthermore", "Moreover", "It's worth noting", "Delve into", "game-changer", "revolutionize", "leverage", "utilize", "In today's digital landscape", "In the ever-evolving", "at the end of the day", "moving the needle", "paradigm shift", "cutting-edge", "seamless", "robust"
- Plain hyphens only in compound adjectives (e.g., well-known, data-driven)
- Bullet points use plain "-" characters only
- Paragraphs: max 3-4 sentences. White space is your friend.
- No section should feel like the previous one. Vary structure: prose, then a list, then a step-by-step, then a callout, then back to prose.

HUMANIZATION TECHNIQUES:
- Specific over generic: "$240K revenue in 6 months" not "significant revenue growth"
- Use analogies and comparisons drawn from everyday life
- Acknowledge what doesn't work, not just what does
- Include minor qualifications: "This won't work for every situation, but..."
- Reference the reader's likely experience
- Occasionally challenge conventional wisdom — have a take
- Name real tools, real platforms, real frameworks where relevant
- Write FAQ answers like you're actually speaking to someone

SEO MASTERY — HARDWIRED:
- Satisfy ALL stated search intents within the article
- Primary keyword: exact match in H1, first 100 words, at least 2 H2s, conclusion
- Secondary keywords: woven naturally into H2s, H3s, and body text
- Keyword density: 1.0-1.8% primary, 0.5-1.0% each secondary
- Answer the core question within the FIRST 200 words
- E-E-A-T signals: cite specific data, describe real-world scenarios
- Featured snippet optimization: at least one clean definition block or numbered list
- Internal linking: 2-3 contextually placed links with descriptive anchor text
- External links: 1-2 authoritative sources

IMAGE PLACEMENT GUIDANCE:
Do NOT generate image prompt blocks. At natural visual breaks, insert:
*[Suggested image: brief specific description]*
Place 2-4 times throughout.

OUTPUT FORMAT: Strict Markdown only. No HTML tags. No image-prompt code blocks."""

    internal_links_context = ""
    if request.internal_links.strip():
        internal_links_context = f"\n<internal_link_targets>\n{request.internal_links}\n</internal_link_targets>"

    user_prompt = f"""Generate a complete, publish-ready SEO blog post.

===== CORE BRIEF =====
<topic>{request.topic}</topic>
<primary_keyword>{request.primary_keyword}</primary_keyword>
<secondary_keywords>{request.secondary_keywords}</secondary_keywords>
<search_intents>{intents_str}</search_intents>
<content_type>{request.content_type}</content_type>
<tone>{request.tone}</tone>
<target_audience>{request.target_audience or 'General audience — infer from context'}</target_audience>
<target_word_count>{request.word_count} words</target_word_count>
<cta_goal>{request.cta_goal or 'Infer from company context and requirements'}</cta_goal>
{internal_links_context}

===== COMPANY & BRAND =====
<company_context>
{request.company_context or 'No company context provided. Write as an expert third-party author.'}
</company_context>

<requirement>
{request.requirement or 'Create a comprehensive, ranking-worthy blog post on this topic.'}
</requirement>

===== COMPETITIVE INTELLIGENCE =====
<competitor_analysis>
{request.competitor_blogs or 'No competitor data provided. Aim for comprehensive coverage of all likely sub-topics.'}
</competitor_analysis>

===== RESEARCH & DATA =====
<research_and_data>
{request.research_data or 'No specific research data provided. Use your expertise and cite plausible industry benchmarks.'}
</research_and_data>

===== SPECIAL INSTRUCTIONS =====
<specific_instructions>
{request.prompt_instructions or 'Follow all system prompt rules. Maximize content quality, human voice, and SEO effectiveness.'}
</specific_instructions>

===== REQUIRED OUTPUT FORMAT =====

STEP 1 — Output this metadata block FIRST:
```seo-meta
META_TITLE: [50-60 chars. Include primary keyword. Genuinely click-worthy.]
META_DESCRIPTION: [140-160 chars. Lead with a concrete benefit. Include primary keyword. Subtle CTA.]
URL_SLUG: [lowercase-hyphenated-slug-with-primary-keyword]
FOCUS_KEYWORD: {request.primary_keyword}
SECONDARY_KEYWORDS: {request.secondary_keywords}
SEARCH_INTENTS: {intents_str}
CONTENT_TYPE: {request.content_type}
ESTIMATED_WORD_COUNT: [your estimate]
```

STEP 2 — Write the full blog post in Markdown:

# [H1: compelling title with primary keyword]

[HERO: 2-3 sharp hook sentences — stat, bold claim, or tension-creating question]

[INTRO: 150-250 words. Define the problem. Signal what reader will learn. Primary keyword in first 100 words. 1 internal link.]

*[Suggested image: opening visual description]*

## [H2 — Featured Snippet Target: direct answer to main query]
[2-4 sentence or numbered-list answer Google can use as snippet. Then expand.]

## [H2 — Core Subtopic 1 with secondary keyword]
### [H3 sub-point]
### [H3 sub-point]

[Continue 4-5 more H2 sections. Mix prose, lists, steps. Specific examples, numbers, real tools.]

*[Suggested image: mid-article visual]*

## [H2 — Practical/Actionable Section]
### [Numbered steps or concrete tips]

## [H2 — Common Mistakes / What Most People Get Wrong]

## [H2 — Real-World Example or Mini Case Study]

## Frequently Asked Questions

**Q: [Most-searched FAQ]**
A: [Direct, conversational answer 2-4 sentences]

**Q: [Second FAQ]**
A: [Direct answer]

**Q: [Third FAQ]**
A: [Direct answer]

## [H2 — Conclusion referencing key insight]
[100-150 words. Key takeaway. Specific CTA: {request.cta_goal or 'drive engagement'}. Forward-looking close.]

---
SILENT CHECKLIST (apply, don't output):
☑ Primary keyword in H1, first 100 words, 2+ H2s, conclusion
☑ All intents ({intents_str}) addressed
☑ Zero em-dashes, zero AI clichés, natural contractions
☑ Max 3-4 sentence paragraphs, varied structure
☑ 1+ specific stat/example per major section
☑ 2-4 image suggestions in italics
☑ 2-3 internal links, 1-2 external authority links
☑ FAQ with 3 real questions
☑ Target word count: {request.word_count}"""

    headers = {"Authorization": f"Bearer {AIML_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": AIML_MODEL,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "temperature": 0.85,
        "max_tokens": 4096
    }

    try:
        response = requests.post(AIML_BASE_URL, headers=headers, json=payload, timeout=180)
        if not response.ok:
            return {"error": f"API error {response.status_code}: {response.text[:500]}", "blog": "", "seo_meta": {}, "seo_score": {}}

        data = response.json()
        if 'choices' in data:
            blog_content = data['choices'][0]['message']['content']
        elif 'content' in data:
            blog_content = data['content'][0]['text']
        else:
            return {"error": f"Unrecognised response format: {str(data)[:300]}", "blog": "", "seo_meta": {}, "seo_score": {}}

        meta = extract_seo_meta(blog_content)
        seo_score = compute_seo_score(blog_content, request.primary_keyword, request.secondary_keywords)
        return {"blog": blog_content, "seo_meta": meta, "seo_score": seo_score}

    except requests.exceptions.RequestException as e:
        return {"error": str(e), "blog": "", "seo_meta": {}, "seo_score": {}}
    except KeyError as e:
        return {"error": f"Unexpected API response key: {str(e)}", "blog": "", "seo_meta": {}, "seo_score": {}}


# == AI Chat / Edit ==

@app.post("/chat")
async def chat_edit(request: ChatRequest):
    system_prompt = f"""You are an expert SEO content editor with 20+ years of experience. You are helping the user refine and improve a blog post.

ORIGINAL BRIEF CONTEXT:
{request.brief_context}

CURRENT BLOG CONTENT:
{request.blog_context}

YOUR ROLE:
- Apply requested edits precisely and surgically
- Maintain existing voice, tone, and SEO structure unless asked to change them
- When rewriting a section: output ONLY that section rewritten in Markdown, preceded by a single sentence confirming the change
- When rewriting the full blog: output the complete blog in Markdown
- Preserve keyword placement and internal links unless instructed otherwise
- Keep image suggestion lines (*[Suggested image: ...]*) unless asked to remove them
- Never add em-dashes, AI clichés, or robotic phrasing
- If the user pastes a selected passage and asks to improve it, return only that passage rewritten

OUTPUT FORMAT: Markdown only. Confirm change in one sentence, then output the revised content."""

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    headers = {"Authorization": f"Bearer {AIML_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": AIML_MODEL,
        "system": system_prompt,
        "messages": messages,
        "temperature": 0.75,
        "max_tokens": 4096
    }

    try:
        response = requests.post(AIML_BASE_URL, headers=headers, json=payload, timeout=180)
        if not response.ok:
            return {"error": f"API error {response.status_code}: {response.text[:500]}", "reply": ""}

        data = response.json()
        if 'choices' in data:
            reply = data['choices'][0]['message']['content']
        elif 'content' in data:
            reply = data['content'][0]['text']
        else:
            return {"error": "Unrecognised response format", "reply": ""}

        return {"reply": reply}

    except Exception as e:
        return {"error": str(e), "reply": ""}


# == Humanize Content ==

@app.post("/humanize")
async def humanize_content(request: HumanizeRequest):
    system_prompt = """You are a veteran journalist and ghostwriter with 25+ years of experience writing for major publications. Your job is to take an AI-generated blog post and rewrite it so it reads like a real human wrote it from scratch.

ABSOLUTE RULES - FOLLOW ALL OF THESE WITHOUT EXCEPTION:

1. REWRITE EVERY SENTENCE. Do not copy-paste from the input. Rephrase everything in your own words.

2. REMOVE ALL AI PATTERNS:
   - No "In conclusion", "Furthermore", "Moreover", "It's worth noting", "Delve into"
   - No "game-changer", "revolutionize", "leverage", "utilize", "robust", "seamless"
   - No "In today's digital landscape", "In the ever-evolving", "at the end of the day"
   - No "paradigm shift", "cutting-edge", "moving the needle"
   - No "comprehensive", "crucial", "essential" used as filler
   - No sentences starting with "This is" or "It is important to"
   - No "Let's dive in" or "Without further ado"

3. REMOVE ALL SPECIAL UNICODE CHARACTERS:
   - No em-dashes or en-dashes. Use commas, periods, or plain hyphens only.
   - No special quote marks. Use straight quotes only.
   - No bullet characters. Use plain "-" only.
   - No ellipsis character. Use three periods "..." if needed.

4. USE ONLY SIMPLE PUNCTUATION: period (.), comma (,), question mark (?), exclamation mark (!), plain hyphen (-), colon (:), semicolon (;), straight quotes

5. WRITE LIKE A REAL PERSON:
   - Mix sentence lengths dramatically. Some very short. Others should meander a bit, building on an idea before landing the point.
   - Use contractions naturally: you're, it's, don't, we've, they're, can't, won't, I've
   - Include personal observations: "I've seen this happen", "In my experience", "What most people miss"
   - Add slight informality: incomplete sentences sometimes. Starting sentences with "And" or "But". Using "pretty" instead of "quite". Saying "a lot" instead of "numerous".
   - Express opinions and mild frustrations: "This drives me crazy", "Honestly, most advice about this is wrong"
   - Use everyday analogies and comparisons
   - Reference real experiences and practical knowledge
   - Include qualifiers that a real person would use: "probably", "most of the time", "in my experience", "tends to"

6. VARY PARAGRAPH STRUCTURE:
   - Some paragraphs should be just 1-2 sentences
   - Others can be 3-4 sentences
   - Never make all paragraphs the same length
   - Break up any wall of text

7. PRESERVE SEO STRUCTURE:
   - Keep the same H1, H2, H3 hierarchy
   - Keep the primary keyword in H1, intro, at least 2 H2s, and conclusion
   - Keep FAQ section intact but rewrite answers conversationally
   - Keep image suggestion markers
   - Keep internal and external links
   - Keep the seo-meta block unchanged

8. PRESERVE THE SAME INFORMATION AND DATA:
   - Keep all statistics, numbers, and data points
   - Keep all tool names and specific references
   - Keep the same overall structure and flow of ideas
   - Don't add new sections or remove existing ones

OUTPUT: The complete rewritten blog in Markdown format. Keep the seo-meta block at the top exactly as-is."""

    user_prompt = f"""Humanize this blog post completely. Rewrite every sentence so it sounds like a real person wrote it, not AI. Follow all the rules in your system prompt strictly.

Here is the blog to humanize:

{request.markdown}"""

    headers = {"Authorization": f"Bearer {AIML_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": AIML_MODEL,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "temperature": 0.92,
        "max_tokens": 4096
    }

    try:
        response = requests.post(AIML_BASE_URL, headers=headers, json=payload, timeout=180)
        if not response.ok:
            return {"error": f"API error {response.status_code}: {response.text[:500]}", "blog": ""}

        data = response.json()
        if 'choices' in data:
            blog_content = data['choices'][0]['message']['content']
        elif 'content' in data:
            blog_content = data['content'][0]['text']
        else:
            return {"error": "Unrecognised response format", "blog": ""}

        # Re-compute SEO score with humanized content
        seo_score = compute_seo_score(blog_content, request.primary_keyword, "")
        meta = extract_seo_meta(blog_content)
        return {"blog": blog_content, "seo_meta": meta, "seo_score": seo_score}

    except Exception as e:
        return {"error": str(e), "blog": ""}


# == Optimize Prompt ==

@app.post("/optimize-prompt")
async def optimize_prompt(request: OptimizePromptRequest):
    system_prompt = """You are a prompt engineering expert who specializes in creating optimized prompts for AI content generation. Your job is to analyze a user's blog configuration inputs and produce a single, clean, highly optimized prompt that would generate better blog output.

RULES:
1. Analyze what the user actually wants based on all their inputs
2. Remove redundancy, fluff, and vague language
3. Produce a structured, clear prompt that:
   - States the exact blog goal in one sentence
   - Specifies the primary and secondary keywords clearly
   - Defines tone and audience precisely
   - Includes any specific requirements or constraints
   - Is formatted for Claude-style prompting (clear sections, specific instructions)
4. The output prompt should be concise but comprehensive
5. Format the optimized prompt in a clean, copy-pasteable format
6. Add any smart suggestions you notice from the inputs (missing angles, better keyword targeting, etc.)

OUTPUT FORMAT:
Return ONLY the optimized prompt text, ready to copy-paste. No explanations before or after.
Start with a brief "SUGGESTIONS" section (3-5 bullet points max) noting improvements, then the full optimized prompt."""

    # Build context from all user inputs
    intents_str = ", ".join(request.search_intents) if request.search_intents else "Not specified"

    user_prompt = f"""Analyze these blog configuration inputs and create an optimized, clean prompt:

TOPIC: {request.topic or '[Not provided]'}
PRIMARY KEYWORD: {request.primary_keyword or '[Not provided]'}
SECONDARY KEYWORDS: {request.secondary_keywords or '[Not provided]'}
SEARCH INTENTS: {intents_str}
CONTENT TYPE: {request.content_type or '[Not provided]'}
TONE: {request.tone or '[Not provided]'}
TARGET AUDIENCE: {request.target_audience or '[Not provided]'}
WORD COUNT: {request.word_count or '[Not provided]'}
CTA GOAL: {request.cta_goal or '[Not provided]'}
COMPANY CONTEXT: {request.company_context[:1000] if request.company_context else '[Not provided]'}
REQUIREMENTS: {request.requirement or '[Not provided]'}
SPECIAL INSTRUCTIONS: {request.prompt_instructions or '[Not provided]'}
INTERNAL LINKS: {request.internal_links or '[Not provided]'}
COMPETITOR BLOGS: {'[Provided - ' + str(len(request.competitor_blogs)) + ' chars]' if request.competitor_blogs else '[Not provided]'}
RESEARCH DATA: {'[Provided - ' + str(len(request.research_data)) + ' chars]' if request.research_data else '[Not provided]'}

Create the optimized prompt now."""

    headers = {"Authorization": f"Bearer {AIML_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": AIML_MODEL,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "temperature": 0.6,
        "max_tokens": 2048
    }

    try:
        response = requests.post(AIML_BASE_URL, headers=headers, json=payload, timeout=120)
        if not response.ok:
            return {"error": f"API error {response.status_code}: {response.text[:500]}", "result": ""}

        data = response.json()
        if 'choices' in data:
            result = data['choices'][0]['message']['content']
        elif 'content' in data:
            result = data['content'][0]['text']
        else:
            return {"error": "Unrecognised response format", "result": ""}

        return {"result": result}

    except Exception as e:
        return {"error": str(e), "result": ""}


# == HTML Export ==

@app.post("/export-html")
async def export_html(request: ExportRequest):
    md = request.markdown
    md = re.sub(r'```seo-meta[\s\S]*?```\n?', '', md).strip()

    lines = md.split('\n')
    html_lines = []
    in_ul = False
    in_ol = False
    buffer = []

    def flush_paragraph():
        nonlocal buffer
        text = ' '.join(buffer).strip()
        if text:
            html_lines.append(f'<p>{inline_format(text)}</p>')
        buffer = []

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            html_lines.append('</ul>')
            in_ul = False
        if in_ol:
            html_lines.append('</ol>')
            in_ol = False

    def inline_format(text: str) -> str:
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*\[Suggested image:\s*([^\]]+)\]\*', r'<!-- Image suggestion: \1 -->', text)
        text = re.sub(r'(?<!\*)\*(?!\[)([^*\n]+?)\*(?!\*)', r'<em>\1</em>', text)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        return text

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if re.match(r'^# [^#]', stripped):
            flush_paragraph(); close_lists()
            html_lines.append(f'<h1>{inline_format(stripped[2:])}</h1>')
            i += 1; continue
        if re.match(r'^## [^#]', stripped):
            flush_paragraph(); close_lists()
            html_lines.append(f'<h2>{inline_format(stripped[3:])}</h2>')
            i += 1; continue
        if re.match(r'^### [^#]', stripped):
            flush_paragraph(); close_lists()
            html_lines.append(f'<h3>{inline_format(stripped[4:])}</h3>')
            i += 1; continue
        if re.match(r'^#### ', stripped):
            flush_paragraph(); close_lists()
            html_lines.append(f'<h4>{inline_format(stripped[5:])}</h4>')
            i += 1; continue
        if re.match(r'^[-*_]{3,}$', stripped):
            flush_paragraph(); close_lists()
            html_lines.append('<hr>')
            i += 1; continue

        ol_match = re.match(r'^\d+\.\s+(.+)', stripped)
        if ol_match:
            flush_paragraph()
            if in_ul: html_lines.append('</ul>'); in_ul = False
            if not in_ol: html_lines.append('<ol>'); in_ol = True
            html_lines.append(f'<li>{inline_format(ol_match.group(1))}</li>')
            i += 1; continue

        ul_match = re.match(r'^[-*+]\s+(.+)', stripped)
        if ul_match:
            flush_paragraph()
            if in_ol: html_lines.append('</ol>'); in_ol = False
            if not in_ul: html_lines.append('<ul>'); in_ul = True
            html_lines.append(f'<li>{inline_format(ul_match.group(1))}</li>')
            i += 1; continue

        if stripped.startswith('> '):
            flush_paragraph(); close_lists()
            html_lines.append(f'<blockquote><p>{inline_format(stripped[2:])}</p></blockquote>')
            i += 1; continue

        if stripped.startswith('```'):
            flush_paragraph(); close_lists()
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                i += 1
            i += 1; continue

        if stripped.startswith('*[Suggested image:') and stripped.endswith(']*'):
            flush_paragraph(); close_lists()
            desc = re.sub(r'^\*\[Suggested image:\s*', '', stripped).rstrip(']*').strip()
            html_lines.append(f'<!-- Image suggestion: {desc} -->')
            i += 1; continue

        if not stripped:
            flush_paragraph(); close_lists()
            i += 1; continue

        close_lists()
        buffer.append(stripped)
        i += 1

    flush_paragraph()
    close_lists()

    body = '\n'.join(html_lines)
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{request.title}</title>
</head>
<body>
<article>
{body}
</article>
</body>
</html>"""

    return {"html": full_html}


# == Helpers ==

def extract_seo_meta(content: str) -> dict:
    meta = {}
    match = re.search(r'```seo-meta\n(.*?)```', content, re.DOTALL)
    if match:
        for line in match.group(1).strip().split('\n'):
            for key, attr in [('META_TITLE:', 'title'), ('META_DESCRIPTION:', 'description'),
                               ('URL_SLUG:', 'slug'), ('FOCUS_KEYWORD:', 'focus_keyword'),
                               ('CONTENT_TYPE:', 'content_type'), ('ESTIMATED_WORD_COUNT:', 'estimated_word_count')]:
                if line.startswith(key):
                    meta[attr] = line.replace(key, '').strip()
    return meta


def compute_seo_score(content: str, primary_kw: str, secondary_kws: str) -> dict:
    clean = re.sub(r'```[\s\S]*?```', '', content)
    words = clean.split()
    word_count = len(words)
    checks = {}

    h1_match = re.search(r'^# (.+)', clean, re.MULTILINE)
    checks['keyword_in_h1'] = primary_kw.lower() in (h1_match.group(1).lower() if h1_match else '')
    checks['keyword_in_intro'] = primary_kw.lower() in ' '.join(words[:100]).lower()
    h2_count = len(re.findall(r'^## ', clean, re.MULTILINE))
    checks['has_multiple_sections'] = h2_count >= 4
    checks['has_faq'] = bool(re.search(r'(FAQ|Frequently Asked)', clean, re.IGNORECASE))
    img_suggestions = len(re.findall(r'\*\[Suggested image:', clean))
    checks['has_image_suggestions'] = img_suggestions >= 2
    checks['has_internal_links'] = len(re.findall(r'\[.+?\]\(/[^h]', clean)) >= 1
    checks['word_count_ok'] = word_count >= 1000
    kw_count = clean.lower().count(primary_kw.lower())
    density = (kw_count / word_count * 100) if word_count > 0 else 0
    checks['keyword_density_ok'] = 0.8 <= density <= 2.5

    passed = sum(1 for v in checks.values() if v)
    score = round((passed / len(checks)) * 100)
    return {"score": score, "checks": checks, "word_count": word_count,
            "h2_count": h2_count, "img_suggestions": img_suggestions,
            "keyword_density": round(density, 2)}


if __name__ == "__main__":
    import os
    print("Starting SEO Blog Studio...")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)