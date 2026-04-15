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

    # === THE ARCHITECT: Senior Content Engineer ===
    system_prompt = """You are a Senior Content Engineer. Your mission is to build a high-performance content asset that dominates search intent for the given topic and keywords.

YOUR IDENTITY:
You are a battle-tested content strategist with 20+ years building rank-ready assets. You've generated millions in organic revenue. You build content like an engineer builds bridges, with precision, load-bearing structure, and zero waste.

KEYWORD PRECISION - ZERO EXCEPTIONS:
- Insert the Primary Keyword EXACTLY in: the H1, the first 100 words, at least two H2 headings, and the final paragraph.
- Secondary keywords: woven naturally into H2s, H3s, and body text.
- Keyword density: 1.0-1.8% primary, 0.5-1.0% each secondary.

THE 2026 RANKING STRUCTURE:

1. THE HOOK (Pattern Interrupt): Open with a shocking statistic, a bold contrarian claim, or a deep-pain question that stops mid-scroll. No generic openings. Hit the reader in the gut within the first two sentences.

2. THE SNIPPET TRAP: Make the FIRST H2 a direct question the searcher is asking. Follow it IMMEDIATELY with a 40-50 word direct answer block designed specifically for Google's featured snippet. Then expand below it.

3. THE ROADMAP: Include a functional Markdown Table of Contents after the introduction, listing all H2s as a bulleted list. This helps both readers and crawlers.

4. THE CORE: Deliver 3-4 deep strategies using H2/H3 headers. EVERY section MUST include:
   - A "**Pro Tip:**" callout with an insider insight
   - A "**Real-World Example:**" with specific, accurate data (company name, metric, timeframe)

5. THE CLEANSE: Do NOT use em-dashes or en-dashes anywhere. Use only commas, periods, and plain hyphens (-). No exceptions.

CONTENT HYGIENE - MANDATORY:
- Write 2-4 line paragraphs maximum. Never write a wall of text.
- Use "-" for ALL bullet lists. No other bullet characters.
- Embed all provided internal links naturally into high-value, descriptive anchor text.
- Use contractions naturally: you're, it's, don't, we've, they're, can't, won't.
- Vary structure: prose, then a list, then a step-by-step, then a callout, then back to prose.
- No section should feel like the previous one in rhythm or format.

VOCABULARY BAN - ABSOLUTE ZERO:
"In conclusion", "Furthermore", "Moreover", "It's worth noting", "Delve into", "game-changer", "revolutionize", "leverage", "utilize", "In today's digital landscape", "In the ever-evolving", "at the end of the day", "moving the needle", "paradigm shift", "cutting-edge", "seamless", "robust", "Unlock", "Harness".

ACCURACY:
- Use only verifiable industry data. If you lack a specific number, describe the industry benchmark with precision (e.g., "industry surveys consistently show adoption rates between 60-75% among mid-market SaaS companies").
- Name real tools, real platforms, real frameworks.
- Cite sources inline where possible.

E-E-A-T SIGNALS:
- First-person experience signals: "In practice", "What I've consistently seen", "Most teams I've worked with"
- Specific data points over vague claims
- Acknowledge limitations and edge cases
- Reference real-world scenarios and case studies

IMAGE PLACEMENT:
At natural visual breaks, insert: *[Suggested image: brief specific description]*
Place 2-4 times throughout. Do NOT generate image prompt blocks.

OUTPUT FORMAT: Strict Markdown only. No HTML tags. No image-prompt code blocks."""

    internal_links_context = ""
    if request.internal_links.strip():
        internal_links_context = f"\n<internal_link_targets>\n{request.internal_links}\n</internal_link_targets>"

    user_prompt = f"""Build a complete, publish-ready, rank-dominating SEO blog post.

===== CORE BRIEF =====
<topic>{request.topic}</topic>
<primary_keyword>{request.primary_keyword}</primary_keyword>
<secondary_keywords>{request.secondary_keywords}</secondary_keywords>
<search_intents>{intents_str}</search_intents>
<content_type>{request.content_type}</content_type>
<tone>{request.tone}</tone>
<target_audience>{request.target_audience or 'General audience - infer the most strategic audience from context'}</target_audience>
<target_word_count>{request.word_count} words</target_word_count>
<cta_goal>{request.cta_goal or 'Infer from company context and requirements'}</cta_goal>
{internal_links_context}

===== COMPANY & BRAND =====
<company_context>
{request.company_context or 'No company context provided. Write as an expert third-party author.'}
</company_context>

<requirement>
{request.requirement or 'Create the definitive, ranking-worthy blog post on this topic that outperforms everything currently on page 1.'}
</requirement>

===== COMPETITIVE INTELLIGENCE =====
<competitor_analysis>
{request.competitor_blogs or 'No competitor data provided. Aim for comprehensive coverage of all likely sub-topics and angle the content to be the most authoritative piece available.'}
</competitor_analysis>

===== RESEARCH & DATA =====
<research_and_data>
{request.research_data or 'No specific research data provided. Use your expertise and cite verifiable industry benchmarks with precision.'}
</research_and_data>

===== SPECIAL INSTRUCTIONS =====
<specific_instructions>
{request.prompt_instructions or 'Follow all system prompt rules. Maximize content quality, human voice, and SEO effectiveness.'}
</specific_instructions>

===== REQUIRED OUTPUT FORMAT =====

STEP 1 - Output this metadata block FIRST:
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

STEP 2 - Write the full blog post in Markdown following this EXACT structure:

# [H1: compelling title with EXACT primary keyword]

[THE HOOK / PATTERN INTERRUPT: 2-3 sentences. Shocking stat, bold contrarian claim, or deep-pain question. Stop them mid-scroll.]

[INTRO: 150-250 words. Primary keyword in first 100 words. Define the problem. Signal what the reader will learn. 1 internal link embedded naturally.]

*[Suggested image: opening visual description]*

## Table of Contents
- [List all H2 sections as bullet points]

## [H2 - THE SNIPPET TRAP: Phrase this as a direct question the searcher is asking]
[DIRECT ANSWER: Exactly 40-50 words. This is your featured snippet bid. Clear, definitive, no fluff.]

[Then expand with 2-3 paragraphs of deeper context.]

## [H2 - Strategy/Subtopic 1 with secondary keyword]
### [H3 sub-point]
**Pro Tip:** [Insider insight]
**Real-World Example:** [Company/scenario with specific data]
### [H3 sub-point]

## [H2 - Strategy/Subtopic 2 with secondary keyword]
### [H3 sub-point]
**Pro Tip:** [Insider insight]
**Real-World Example:** [Company/scenario with specific data]

*[Suggested image: mid-article visual]*

## [H2 - Strategy/Subtopic 3]
### [H3 sub-point]
**Pro Tip:** [Insider insight]
**Real-World Example:** [Company/scenario with specific data]

## [H2 - Common Mistakes / What Most People Get Wrong]
[3-5 mistakes as a numbered or bulleted list with brief explanations]

## [H2 - Actionable Takeaways / Step-by-Step]
[Numbered steps or concrete tips the reader can implement today]

## Frequently Asked Questions

**Q: [Most-searched FAQ related to primary keyword]**
A: [Direct, conversational answer 2-4 sentences]

**Q: [Second FAQ]**
A: [Direct answer]

**Q: [Third FAQ]**
A: [Direct answer]

## [H2 - Conclusion with primary keyword in heading]
[100-150 words. Key takeaway with primary keyword. Specific CTA: {request.cta_goal or 'drive engagement'}. Forward-looking close.]

---
SILENT CHECKLIST (apply, don't output):
- Primary keyword EXACT in H1, first 100 words, 2+ H2s, final paragraph
- Pattern Interrupt hook in first 2 sentences
- Snippet Trap: first H2 is a question with 40-50 word direct answer
- Table of Contents present
- Every core section has Pro Tip + Real-World Example
- Zero em-dashes, zero en-dashes, zero AI cliches
- All intents ({intents_str}) addressed
- 2-4 line paragraphs max, varied structure
- "-" for all bullet lists
- All internal links embedded in high-value anchor text
- 2-4 image suggestions in italics
- 3 FAQ questions
- Target word count: {request.word_count}"""

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
        blog_content = clean_ai_characters(blog_content)
        seo_score = compute_seo_score(blog_content, request.primary_keyword, request.secondary_keywords)
        return {"blog": blog_content, "seo_meta": meta, "seo_score": seo_score}

    except requests.exceptions.RequestException as e:
        return {"error": str(e), "blog": "", "seo_meta": {}, "seo_score": {}}
    except KeyError as e:
        return {"error": f"Unexpected API response key: {str(e)}", "blog": "", "seo_meta": {}, "seo_score": {}}


# == AI Chat / Edit ==

@app.post("/chat")
async def chat_edit(request: ChatRequest):
    system_prompt = f"""You are an expert SEO content editor. You already have ALL the context you need. NEVER ask the user to paste or share the blog. You ALREADY have the full blog content and the original brief below.

IMPORTANT: You have the COMPLETE blog right here. Do NOT say "paste your content" or "share your blog" or anything similar. You ALREADY HAVE IT. Just do the edit directly.

ORIGINAL BRIEF:
{request.brief_context}

FULL CURRENT BLOG CONTENT (you have this, use it directly):
{request.blog_context}

YOUR RULES:
- Apply requested edits DIRECTLY to the blog content above. You have it. Use it.
- When asked to replace characters (like em-dashes), do it immediately on the blog content you have.
- When rewriting a section: output ONLY that section rewritten in Markdown, preceded by a single sentence confirming the change.
- When rewriting the full blog or making global changes: output the COMPLETE modified blog in Markdown.
- Preserve keyword placement, internal links, SEO structure unless told otherwise.
- Keep image suggestion lines (*[Suggested image: ...]*) unless asked to remove them.
- NEVER use em-dashes, en-dashes, smart quotes, or AI cliches in your output.
- Use only: periods, commas, question marks, exclamation marks, plain hyphens, colons.

OUTPUT FORMAT: Markdown only. One sentence confirming the change, then the revised content."""

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

        return {"reply": clean_ai_characters(reply)}

    except Exception as e:
        return {"error": str(e), "reply": ""}


# == Humanize Content ==

@app.post("/humanize")
async def humanize_content(request: HumanizeRequest):
    # === THE GHOSTWRITER: World-Class Investigative Journalist ===
    system_prompt = """You are a world-class investigative journalist and ghostwriter. Your single mission is to erase every trace of AI "fingerprinting" from this blog post to achieve a 0% AI detection score. You must rewrite the content so thoroughly that no AI detector on Earth can flag it.

LINGUISTIC CHAOS - OBLITERATE THE ROBOTIC RHYTHM:
- Alternate between very short, punchy sentences (3-5 words) and long, complex, comma-heavy observations that build, layer, and land with texture.
- Never let two consecutive sentences have the same length or rhythm.
- Some paragraphs are just one sentence. Others sprawl across 3-4 lines.
- Break predictable cadence. AI writes in metronomic patterns. You write like jazz.

THE "I" FACTOR - FIRST PERSON, ALWAYS:
- Write from a first-person perspective: "I've seen," "My experience shows," "I learned this the hard way," "What I tell my clients."
- Start sentences with "And," "But," or "Because" to mimic natural human speech patterns.
- Use incomplete thoughts sometimes. Trail off. Pick back up.
- Express genuine opinions: "Honestly, this frustrates me," "I'm skeptical of anyone who says otherwise."

THE VOCABULARY PURGE - KILL THESE WORDS ON SIGHT:
Delete EVERY instance of: "Moreover," "Furthermore," "In conclusion," "Unlock," "Harness," "Delve," "Comprehensive," "Crucial," "Essential" (as filler), "game-changer," "revolutionize," "leverage," "utilize," "robust," "seamless," "cutting-edge," "paradigm shift," "In today's digital landscape," "In the ever-evolving," "at the end of the day," "moving the needle," "It's worth noting," "Let's dive in," "Without further ado."
If a word sounds like a "marketing buzzword," kill it. Replace with plain, everyday language.

CHARACTER CONSTRAINTS - STRICT:
- Use ONLY standard English letters, numbers, and basic punctuation: period (.), comma (,), question mark (?), exclamation mark (!), plain hyphen (-).
- Do NOT use em-dashes, en-dashes, or fancy "smart" quotes. Ever.
- No special Unicode characters. No bullet characters. Use plain "-" for lists.
- No ellipsis character. Use three periods "..." if needed.
- Straight quotes only.

HUMAN SPEECH PATTERNS:
- Contractions everywhere: you're, it's, don't, we've, they're, can't, won't, I've, I'd, shouldn't
- Qualifiers a real person uses: "probably," "most of the time," "in my experience," "tends to," "pretty much"
- Everyday analogies, not textbook explanations
- Say "a lot" instead of "numerous." Say "pretty" instead of "quite." Say "big" instead of "significant."
- Reference real frustrations and practical knowledge

PRESERVATION - NON-NEGOTIABLE:
- Keep all keywords in their EXACT structural locations (H1, H2s, intro, conclusion). Do not move them.
- Keep all internal and external links exactly where they are.
- Keep the seo-meta block at the top completely unchanged.
- Keep all statistics, numbers, data points, tool names, and specific references.
- Keep the same H1, H2, H3 hierarchy and section structure.
- Keep FAQ section but rewrite answers conversationally in first person.
- Keep image suggestion markers (*[Suggested image: ...]*) exactly as-is.
- Keep Pro Tip and Real-World Example sections but rewrite their content.
- Do NOT add new sections or remove existing ones.

REWRITE EVERY SINGLE WORD surrounding the preserved keywords and links. Not a single original AI-generated sentence should survive unchanged.

OUTPUT: The complete rewritten blog in Markdown format. Keep the seo-meta block at the top exactly as-is."""

    user_prompt = f"""Humanize this blog post completely. Your goal is 0% AI detection score. Rewrite EVERY sentence.

CRITICAL RULES:
1. Rewrite every sentence, no exceptions. Not a single original AI sentence survives.
2. Use ONLY these characters: a-z, A-Z, 0-9, period, comma, question mark, exclamation mark, plain hyphen, colon, apostrophe, straight quotes. NOTHING ELSE.
3. NO em-dashes, NO en-dashes, NO smart quotes, NO special Unicode. Plain ASCII only.
4. Vary sentence length wildly. Some 3 words. Some 30+ words with multiple commas.
5. Write in first person. Use "I've", "my experience", "I learned".
6. Start sentences with "And", "But", "Because" frequently.
7. Kill every AI buzzword: Moreover, Furthermore, Delve, Unlock, Harness, Comprehensive, Crucial, Essential, Robust, Seamless.

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

        # CRITICAL: Strip all AI-typical UTF characters after humanization
        blog_content = clean_ai_characters(blog_content)

        # Re-compute SEO score with humanized content
        seo_score = compute_seo_score(blog_content, request.primary_keyword, "")
        meta = extract_seo_meta(blog_content)
        return {"blog": blog_content, "seo_meta": meta, "seo_score": seo_score}

    except Exception as e:
        return {"error": str(e), "blog": ""}


# == The Strategist: Optimize Inputs ==

@app.post("/optimize-prompt")
async def optimize_prompt(request: OptimizePromptRequest):
    # === THE STRATEGIST: Lead SEO Strategist ===
    system_prompt = """You are the Lead SEO Strategist. Your word is final. You do not ask questions. You set the standard.

YOUR MANDATE:
Analyze the given topic and keywords. Based on your expert analysis of what it takes to beat the current top 3 results on Google for this topic, you will DICTATE the optimal values for: Tone, Word Count, Target Audience, Content Type, CTA Goal, and Special Writing Instructions.

PROTECT THE FOUNDATION - NEVER ALTER:
- Primary Keyword (keep exactly as provided)
- Blog Topic (keep exactly as provided)
- Secondary Keywords (keep exactly as provided)
- Internal Links (keep exactly as provided)

DICTATE THE WIN:
- Override the user's "Tone", "Word Count", and "Target Audience" with the EXACT parameters required to outrank the current top 3 results on Google.
- Define a hyper-specific target audience (not "marketers" but "Series A SaaS founders with 10-50 employees who are transitioning from paid acquisition to organic").
- Define a high-authority expert tone descriptor (not "professional" but "Field-tested CTO" or "Senior Data Scientist with 15 years in ML ops").
- Set the word count to whatever is strategically required to comprehensively cover the topic and outperform competitors.
- Choose the content type that will rank best for these keywords.
- Define a CTA that aligns with the company context and converts.
- Write special instructions that give the content writer a strategic edge.

OUTPUT FORMAT - STRICT JSON ONLY:
You MUST respond with ONLY a valid JSON object. No markdown, no code fences, no explanation before or after. Just the raw JSON object:

{
  "ranking_logic": "[2-4 paragraphs explaining your strategic analysis: why you chose these specific parameters, what the top results are doing, what gap you're exploiting, and why your chosen parameters will win. Write this like a strategy brief to a CEO.]",
  "tone": "[MUST be one of: authoritative-conversational, friendly-approachable, bold-direct, formal-professional, storytelling-narrative, witty-engaging]",
  "tone_descriptor": "[Your hyper-specific expert persona, e.g., 'Field-tested CTO who has scaled 3 startups from 0 to $10M ARR']",
  "word_count": "[MUST be one of: 800-1200, 1500-2000, 2500-3500, 4000+]",
  "target_audience": "[Hyper-specific audience definition, 1-2 sentences]",
  "content_type": "[MUST be one of: comprehensive-guide, how-to-guide, listicle, comparison, case-study, opinion-thought-leadership, product-review, news-roundup, faq-page, pillar-page]",
  "cta_goal": "[Specific, conversion-oriented CTA aligned with topic and audience]",
  "prompt_instructions": "[3-5 strategic special instructions for the content writer that will give the content a ranking edge. Be specific and actionable.]"
}

Remember: Output ONLY the JSON object. Nothing else."""

    # Build context from all user inputs
    intents_str = ", ".join(request.search_intents) if request.search_intents else "Not specified"

    user_prompt = f"""Analyze this blog configuration and DICTATE the winning parameters. Study the topic and keywords, then override Tone, Word Count, Target Audience, Content Type, CTA Goal, and Special Instructions with what will actually win in search.

TOPIC: {request.topic or '[Not provided]'}
PRIMARY KEYWORD: {request.primary_keyword or '[Not provided]'}
SECONDARY KEYWORDS: {request.secondary_keywords or '[Not provided]'}
SEARCH INTENTS: {intents_str}
CURRENT CONTENT TYPE: {request.content_type or '[Not provided]'}
CURRENT TONE: {request.tone or '[Not provided]'}
CURRENT TARGET AUDIENCE: {request.target_audience or '[Not provided]'}
CURRENT WORD COUNT: {request.word_count or '[Not provided]'}
CURRENT CTA GOAL: {request.cta_goal or '[Not provided]'}
COMPANY CONTEXT: {request.company_context[:1500] if request.company_context else '[Not provided]'}
REQUIREMENTS: {request.requirement or '[Not provided]'}
CURRENT SPECIAL INSTRUCTIONS: {request.prompt_instructions or '[Not provided]'}
INTERNAL LINKS: {request.internal_links or '[Not provided]'}
COMPETITOR BLOGS: {'[Provided - ' + str(len(request.competitor_blogs)) + ' chars of competitor content to analyze]' if request.competitor_blogs else '[Not provided - analyze based on your knowledge of top-ranking content for this topic]'}
RESEARCH DATA: {'[Provided - ' + str(len(request.research_data)) + ' chars]' if request.research_data else '[Not provided]'}

Respond with ONLY the JSON object. No markdown fences. No explanation."""

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
            return {"error": f"API error {response.status_code}: {response.text[:500]}", "strategy": None}

        data = response.json()
        if 'choices' in data:
            result_text = data['choices'][0]['message']['content']
        elif 'content' in data:
            result_text = data['content'][0]['text']
        else:
            return {"error": "Unrecognised response format", "strategy": None}

        # Parse the JSON response from the strategist
        # Strip any markdown code fences if the model added them
        clean_text = result_text.strip()
        if clean_text.startswith('```'):
            clean_text = re.sub(r'^```(?:json)?\s*', '', clean_text)
            clean_text = re.sub(r'\s*```$', '', clean_text)

        try:
            strategy = json.loads(clean_text)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                try:
                    strategy = json.loads(json_match.group())
                except json.JSONDecodeError:
                    return {"error": "Failed to parse strategist response as JSON", "strategy": None, "raw": result_text}
            else:
                return {"error": "Strategist did not return valid JSON", "strategy": None, "raw": result_text}

        return {"strategy": strategy}

    except Exception as e:
        return {"error": str(e), "strategy": None}


# == HTML Export ==

@app.post("/export-html")
async def export_html(request: ExportRequest):
    md = request.markdown
    # Clean AI characters first
    md = clean_ai_characters(md)
    # Remove seo-meta block
    md = re.sub(r'```seo-meta[\s\S]*?```\n?', '', md).strip()
    # Remove Table of Contents section entirely
    md = re.sub(r'^## Table of Contents\s*\n(?:[-*]\s+.*\n)*', '', md, flags=re.MULTILINE)
    # Remove image suggestion lines
    md = re.sub(r'\*\[Suggested image:[^\]]*\]\*\s*\n?', '', md)

    lines = md.split('\n')
    html_lines = []
    in_ul = False
    in_ol = False
    buffer = []

    def flush_paragraph():
        nonlocal buffer
        text = ' '.join(buffer).strip()
        if text:
            html_lines.append(f'  <p>{inline_format(text)}</p>')
        buffer = []

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            html_lines.append('  </ul>')
            in_ul = False
        if in_ol:
            html_lines.append('  </ol>')
            in_ol = False

    def inline_format(text: str) -> str:
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'(?<!\*)\*(?!\[)([^*\n]+?)\*(?!\*)', r'<em>\1</em>', text)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        return text

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            flush_paragraph(); close_lists()
            i += 1; continue

        # Headings
        if re.match(r'^# [^#]', stripped):
            flush_paragraph(); close_lists()
            html_lines.append(f'  <h1>{inline_format(stripped[2:])}</h1>')
            i += 1; continue
        if re.match(r'^## [^#]', stripped):
            flush_paragraph(); close_lists()
            html_lines.append(f'')
            html_lines.append(f'  <h2>{inline_format(stripped[3:])}</h2>')
            i += 1; continue
        if re.match(r'^### [^#]', stripped):
            flush_paragraph(); close_lists()
            html_lines.append(f'  <h3>{inline_format(stripped[4:])}</h3>')
            i += 1; continue
        if re.match(r'^#### ', stripped):
            flush_paragraph(); close_lists()
            html_lines.append(f'  <h4>{inline_format(stripped[5:])}</h4>')
            i += 1; continue

        # Horizontal rules
        if re.match(r'^[-*_]{3,}$', stripped):
            flush_paragraph(); close_lists()
            html_lines.append('  <hr>')
            i += 1; continue

        # Ordered list
        ol_match = re.match(r'^\d+\.\s+(.+)', stripped)
        if ol_match:
            flush_paragraph()
            if in_ul: html_lines.append('  </ul>'); in_ul = False
            if not in_ol: html_lines.append('  <ol>'); in_ol = True
            html_lines.append(f'    <li>{inline_format(ol_match.group(1))}</li>')
            i += 1; continue

        # Unordered list
        ul_match = re.match(r'^[-*+]\s+(.+)', stripped)
        if ul_match:
            flush_paragraph()
            if in_ol: html_lines.append('  </ol>'); in_ol = False
            if not in_ul: html_lines.append('  <ul>'); in_ul = True
            html_lines.append(f'    <li>{inline_format(ul_match.group(1))}</li>')
            i += 1; continue

        # Blockquotes
        if stripped.startswith('> '):
            flush_paragraph(); close_lists()
            html_lines.append(f'  <blockquote><p>{inline_format(stripped[2:])}</p></blockquote>')
            i += 1; continue

        # Code blocks - skip entirely
        if stripped.startswith('```'):
            flush_paragraph(); close_lists()
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                i += 1
            i += 1; continue

        # Regular text -> paragraph buffer
        close_lists()
        buffer.append(stripped)
        i += 1

    flush_paragraph()
    close_lists()

    body = '\n'.join(html_lines)

    # Extract meta for the HTML head
    meta_desc = ''
    meta_match = re.search(r'META_DESCRIPTION:\s*(.+)', request.markdown)
    if meta_match:
        meta_desc = meta_match.group(1).strip().strip('[]')

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{request.title}</title>
  <meta name="description" content="{meta_desc}">
</head>
<body>

<article>
{body}
</article>

</body>
</html>"""

    return {"html": full_html}


# == Helpers ==

def clean_ai_characters(text: str) -> str:
    """Strip all AI-typical UTF characters that trigger AI detection.
    Replaces em-dashes, en-dashes, smart quotes, bullet chars, etc.
    with plain ASCII equivalents."""
    if not text:
        return text
    # Preserve the seo-meta block as-is
    meta_match = re.search(r'```seo-meta[\s\S]*?```', text)
    meta_block = meta_match.group() if meta_match else None
    if meta_block:
        text = text.replace(meta_block, '<<<SEO_META_PLACEHOLDER>>>')

    # Em-dashes and en-dashes -> comma or hyphen
    text = text.replace('\u2014', ', ')   # em-dash -> comma space
    text = text.replace('\u2013', '-')    # en-dash -> plain hyphen
    text = text.replace('\u2012', '-')    # figure dash
    text = text.replace('\u2015', ', ')   # horizontal bar

    # Smart quotes -> straight quotes
    text = text.replace('\u201c', '"')    # left double
    text = text.replace('\u201d', '"')    # right double
    text = text.replace('\u201e', '"')    # low double
    text = text.replace('\u201f', '"')    # high reversed double
    text = text.replace('\u2018', "'")    # left single
    text = text.replace('\u2019', "'")    # right single (curly apostrophe)
    text = text.replace('\u201a', "'")    # low single
    text = text.replace('\u201b', "'")    # high reversed single
    text = text.replace('\u0060', "'")    # backtick to apostrophe

    # Ellipsis character -> three dots
    text = text.replace('\u2026', '...')

    # Bullet characters -> plain hyphen
    text = text.replace('\u2022', '-')    # bullet
    text = text.replace('\u2023', '-')    # triangular bullet
    text = text.replace('\u25e6', '-')    # white bullet
    text = text.replace('\u2043', '-')    # hyphen bullet
    text = text.replace('\u204c', '-')    # black leftwards bullet
    text = text.replace('\u204d', '-')    # black rightwards bullet

    # Arrows -> plain text
    text = text.replace('\u2192', '->')   # right arrow
    text = text.replace('\u2190', '<-')   # left arrow
    text = text.replace('\u21d2', '=>')   # double right arrow

    # Special spaces -> regular space
    text = text.replace('\u00a0', ' ')    # non-breaking space
    text = text.replace('\u2003', ' ')    # em space
    text = text.replace('\u2002', ' ')    # en space
    text = text.replace('\u2009', ' ')    # thin space
    text = text.replace('\u200a', ' ')    # hair space
    text = text.replace('\u200b', '')     # zero-width space
    text = text.replace('\ufeff', '')     # zero-width no-break space (BOM)

    # Misc special chars
    text = text.replace('\u00b7', '-')    # middle dot
    text = text.replace('\u2011', '-')    # non-breaking hyphen
    text = text.replace('\u2010', '-')    # hyphen
    text = text.replace('\u2212', '-')    # minus sign

    # Checkmarks and crosses
    text = text.replace('\u2713', 'yes')  # checkmark
    text = text.replace('\u2714', 'yes')  # heavy checkmark
    text = text.replace('\u2717', 'no')   # cross
    text = text.replace('\u2718', 'no')   # heavy cross
    text = text.replace('\u2611', 'yes')  # ballot box with check
    text = text.replace('\u2610', 'no')   # ballot box

    # Clean double commas or weird spacing from replacements
    text = re.sub(r',\s*,', ',', text)
    text = re.sub(r'\s{2,}', ' ', text)
    # Fix comma at start of sentence after heading replacement
    text = re.sub(r'^(#+\s+.*), ', r'\1 ', text, flags=re.MULTILINE)

    # Restore seo-meta block
    if meta_block:
        text = text.replace('<<<SEO_META_PLACEHOLDER>>>', meta_block)

    return text

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
    print("Starting SEO Blog Studio...")
    print("Go to: http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)