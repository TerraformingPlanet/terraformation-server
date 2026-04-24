"""
query_llm_leaderboard.py — Filtre le Berkeley Function Calling Leaderboard (BFCL)
pour trouver des modèles open-source adaptés aux agents Terraformation.

Le BFCL mesure la qualité de function/tool calling — exactement ce que
Terraformation utilise avec LLM_MODE=tools.

Usage:
    python Tools/query_llm_leaderboard.py
    python Tools/query_llm_leaderboard.py --top 20
    python Tools/query_llm_leaderboard.py --keyword qwen
    python Tools/query_llm_leaderboard.py --fc-only          # FC natif uniquement
    python Tools/query_llm_leaderboard.py --open-only        # open-source uniquement
"""
import argparse
import re
import urllib.request

# ── Config ─────────────────────────────────────────────────────────────────────

BFCL_URL = "https://gorilla.cs.berkeley.edu/leaderboard.html"

# Licences considérées comme open-source / utilisables localement
_OPEN_LICENSES = {
    "apache-2.0", "mit", "modified-mit", "cc-by-nc-4.0", "cc-by-nc",
    "apache 2.0", "gemma-terms-of-use", "falcon-llm-license",
    "meta llama 3 community", "meta llama 4 community",
    "nvidia-open-model-license", "katanemo-research",
    "cc-by-nc 4.0 license (w/ acceptable use addendum)",
    "qwen-research",
}

# ── Helpers ────────────────────────────────────────────────────────────────────


def _fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "terraformation-tool/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


"""
query_llm_leaderboard.py — Filtre le Berkeley Function Calling Leaderboard (BFCL)
pour trouver des modèles open-source adaptés aux agents Terraformation.

Le BFCL mesure la qualité de function/tool calling — exactement ce que
Terraformation utilise avec LLM_MODE=tools.

Snapshot embarqué : 12 avril 2026 (gorilla.cs.berkeley.edu/leaderboard.html)
La page est JS-rendered, donc les données sont embarquées statiquement.

Usage:
    python Tools/query_llm_leaderboard.py
    python Tools/query_llm_leaderboard.py --top 20
    python Tools/query_llm_leaderboard.py --keyword qwen
    python Tools/query_llm_leaderboard.py --fc-only          # FC natif uniquement
    python Tools/query_llm_leaderboard.py --open-only        # open-source uniquement
    python Tools/query_llm_leaderboard.py --min-score 40
"""
import argparse

# ── Licences open-source / utilisables localement ─────────────────────────────

_OPEN_LICENSES = {
    "apache-2.0", "mit", "modified-mit", "cc-by-nc-4.0", "cc-by-nc",
    "apache 2.0", "gemma-terms-of-use", "falcon-llm-license",
    "meta llama 3 community", "meta llama 4 community",
    "nvidia-open-model-license", "katanemo-research",
    "cc-by-nc 4.0 license (w/ acceptable use addendum)",
    "qwen-research",
}

# ── Snapshot BFCL — 12 avril 2026 ─────────────────────────────────────────────
# Source: https://gorilla.cs.berkeley.edu/leaderboard.html
# Colonnes: rank, score_overall, model, mode (FC/Prompt), org, license

_BFCL_DATA = [
    # rank  score   model                                           mode      org             license
    (1,  77.47, "Claude-Opus-4-5-20251101",                       "FC",     "Anthropic",    "proprietary"),
    (2,  73.24, "Claude-Sonnet-4-5-20250929",                     "FC",     "Anthropic",    "proprietary"),
    (3,  72.51, "Gemini-3-Pro-Preview",                           "Prompt", "Google",       "proprietary"),
    (4,  72.38, "GLM-4.6",                                        "FC",     "Zhipu AI",     "mit"),
    (5,  69.57, "Grok-4-1-fast-reasoning",                        "FC",     "xAI",          "proprietary"),
    (6,  68.70, "Claude-Haiku-4-5-20251001",                      "FC",     "Anthropic",    "proprietary"),
    (7,  68.14, "Gemini-3-Pro-Preview",                           "FC",     "Google",       "proprietary"),
    (8,  63.05, "o3-2025-04-16",                                  "Prompt", "OpenAI",       "proprietary"),
    (9,  62.97, "Grok-4-0709",                                    "Prompt", "xAI",          "proprietary"),
    (10, 61.38, "Grok-4-0709",                                    "FC",     "xAI",          "proprietary"),
    (11, 59.06, "Moonshotai-Kimi-K2-Instruct",                    "FC",     "MoonshotAI",   "modified-mit"),
    (12, 58.29, "Grok-4-1-fast-non-reasoning",                    "FC",     "xAI",          "proprietary"),
    (13, 57.06, "Command A Reasoning",                            "FC",     "Cohere",       "cc-by-nc 4.0 license (w/ acceptable use addendum)"),
    (14, 56.73, "DeepSeek-V3.2-Exp (Prompt + Thinking)",         "Prompt", "DeepSeek",     "mit"),
    (15, 56.24, "Gemini-2.5-Flash",                              "FC",     "Google",       "proprietary"),
    (16, 55.87, "GPT-5.2-2025-12-11",                            "FC",     "OpenAI",       "proprietary"),
    (17, 55.46, "GPT-5-mini-2025-08-07",                         "FC",     "OpenAI",       "proprietary"),
    (18, 54.66, "xLAM-2-32b-fc-r",                               "FC",     "Salesforce",   "cc-by-nc-4.0"),
    (19, 54.12, "DeepSeek-V3.2-Exp",                             "FC",     "DeepSeek",     "mit"),
    (20, 53.96, "GPT-4.1-2025-04-14",                            "FC",     "OpenAI",       "proprietary"),
    (21, 53.24, "o4-mini-2025-04-16",                            "FC",     "OpenAI",       "proprietary"),
    (22, 53.07, "xLAM-2-70b-fc-r",                               "FC",     "Salesforce",   "cc-by-nc-4.0"),
    (23, 52.15, "Qwen3-235B-A22B-Instruct-2507",                 "Prompt", "Qwen",         "apache-2.0"),
    (24, 51.45, "GPT-5-nano-2025-08-07",                         "FC",     "OpenAI",       "proprietary"),
    (25, 51.40, "Nanbeige4-3B-Thinking-2511",                    "FC",     "Nanbeige",     "apache-2.0"),
    (26, 50.90, "Gemini-2.5-Flash",                              "Prompt", "Google",       "proprietary"),
    (27, 50.45, "GPT-4.1-mini-2025-04-14",                      "FC",     "OpenAI",       "proprietary"),
    (28, 50.26, "o4-mini-2025-04-16",                            "Prompt", "OpenAI",       "proprietary"),
    (29, 48.71, "Qwen3-32B",                                     "FC",     "Qwen",         "apache-2.0"),
    (30, 48.56, "o3-2025-04-16",                                 "FC",     "OpenAI",       "proprietary"),
    (31, 47.99, "Qwen3-235B-A22B-Instruct-2507",                 "FC",     "Qwen",         "apache-2.0"),
    (32, 47.68, "Nanbeige3.5-Pro-Thinking",                      "FC",     "Nanbeige",     "apache-2.0"),
    (33, 46.78, "Qwen3-32B",                                     "Prompt", "Qwen",         "apache-2.0"),
    (34, 46.68, "xLAM-2-8b-fc-r",                                "FC",     "Salesforce",   "cc-by-nc-4.0"),
    (35, 46.49, "Command A",                                     "FC",     "Cohere",       "cc-by-nc 4.0 license (w/ acceptable use addendum)"),
    (36, 46.23, "BitAgent-Bounty-8B",                            "FC",     "Bittensor",    "apache-2.0"),
    (37, 45.37, "Arch-Agent-32B",                                "FC",     "katanemo",     "katanemo-research"),
    (38, 45.27, "GPT-5.2-2025-12-11",                            "Prompt", "OpenAI",       "proprietary"),
    (39, 42.57, "Qwen3-8B",                                      "FC",     "Qwen",         "apache-2.0"),
    (40, 42.44, "ToolACE-2-8B",                                  "FC",     "Huawei Noah",  "apache-2.0"),
    (41, 41.39, "Qwen3-30B-A3B-Instruct-2507",                   "FC",     "Qwen",         "apache-2.0"),
    (42, 41.22, "xLAM-2-3b-fc-r",                                "FC",     "Salesforce",   "cc-by-nc-4.0"),
    (43, 41.03, "Qwen3-14B",                                     "FC",     "Qwen",         "apache-2.0"),
    (44, 40.43, "Qwen3-8B",                                      "Prompt", "Qwen",         "apache-2.0"),
    (45, 39.38, "GPT-4.1-2025-04-14",                            "Prompt", "OpenAI",       "proprietary"),
    (46, 38.37, "mistral-large-2411",                            "FC",     "Mistral AI",   "proprietary"),
    (47, 37.77, "Qwen3-14B",                                     "Prompt", "Qwen",         "apache-2.0"),
    (48, 37.69, "Mistral-Medium-2505",                           "Prompt", "Mistral AI",   "proprietary"),
    (49, 37.56, "Mistral-Medium-2505",                           "FC",     "Mistral AI",   "proprietary"),
    (50, 37.29, "Llama-4-Maverick-17B-128E-Instruct-FP8",        "FC",     "Meta",         "meta llama 4 community"),
    (51, 37.15, "Mistral-small-2506",                            "FC",     "Mistral AI",   "proprietary"),
    (52, 36.87, "Gemini-2.5-Flash-Lite",                         "FC",     "Google",       "proprietary"),
    (53, 36.70, "Qwen3-30B-A3B-Instruct-2507",                   "Prompt", "Qwen",         "apache-2.0"),
    (54, 35.68, "Qwen3-4B-Instruct-2507",                        "FC",     "Qwen",         "apache-2.0"),
    (55, 35.52, "Qwen3-4B-Instruct-2507",                        "Prompt", "Qwen",         "apache-2.0"),
    (56, 35.36, "Arch-Agent-3B",                                 "FC",     "katanemo",     "katanemo-research"),
    (57, 33.47, "Claude-Opus-4-5-20251101",                      "Prompt", "Anthropic",    "proprietary"),
    (58, 33.05, "GPT-4.1-nano-2025-04-14",                       "FC",     "OpenAI",       "proprietary"),
    (59, 32.38, "Mistral-Small-2506",                            "Prompt", "Mistral AI",   "proprietary"),
    (60, 32.14, "Arch-Agent-1.5B",                               "FC",     "katanemo",     "katanemo-research"),
    (61, 32.07, "Command R7B",                                   "FC",     "Cohere",       "cc-by-nc-4.0"),
    (62, 31.90, "Llama-3.3-70B-Instruct",                        "FC",     "Meta",         "meta llama 3 community"),
    (63, 31.84, "mistral-large-2411",                            "Prompt", "Mistral AI",   "proprietary"),
    (64, 31.67, "Hammer2.1-7b",                                  "FC",     "MadeAgents",   "cc-by-nc-4.0"),
    (65, 30.44, "xLAM-2-1b-fc-r",                                "FC",     "Salesforce",   "cc-by-nc-4.0"),
    (66, 30.43, "Gemma-3-12b-it",                                "Prompt", "Google",       "gemma-terms-of-use"),
    (67, 29.73, "GPT-4.1-mini-2025-04-14",                      "Prompt", "OpenAI",       "proprietary"),
    (68, 29.71, "Hammer2.1-3b",                                  "FC",     "MadeAgents",   "qwen-research"),
    (69, 29.47, "Gemma-3-27b-it",                                "Prompt", "Google",       "gemma-terms-of-use"),
    (70, 28.79, "Phi-4",                                         "Prompt", "Microsoft",    "mit"),
    (71, 28.41, "Qwen3-1.7B",                                    "FC",     "Qwen",         "apache-2.0"),
    (72, 28.13, "Llama-4-Scout-17B-16E-Instruct",                "FC",     "Meta",         "meta llama 4 community"),
    (73, 28.03, "Gemini-2.5-Flash-Lite",                         "Prompt", "Google",       "proprietary"),
    (74, 27.99, "CoALM-70B",                                     "FC",     "UIUC + Oumi",  "meta llama 3 community"),
    (75, 27.88, "Hammer2.1-1.5b",                                "FC",     "MadeAgents",   "cc-by-nc-4.0"),
    (76, 27.87, "palmyra-x-004",                                 "FC",     "Writer",       "proprietary"),
    (77, 27.83, "GPT-5-mini-2025-08-07",                         "Prompt", "OpenAI",       "proprietary"),
    (78, 27.63, "Open-Mistral-Nemo-2407",                        "FC",     "Mistral AI",   "proprietary"),
    (79, 27.55, "GPT-5-nano-2025-08-07",                         "Prompt", "OpenAI",       "proprietary"),
    (80, 27.10, "Amazon-Nova-2-Lite-v1:0",                       "FC",     "Amazon",       "proprietary"),
    (81, 27.10, "Granite-3.1-8B-Instruct",                       "FC",     "IBM",          "apache-2.0"),
    (82, 27.01, "Falcon3-10B-Instruct",                          "FC",     "TII UAE",      "falcon-llm-license"),
    (83, 26.87, "Granite-3.2-8B-Instruct",                       "FC",     "IBM",          "apache-2.0"),
    (84, 26.81, "CoALM-8B",                                      "FC",     "UIUC + Oumi",  "meta llama 3 community"),
    (85, 25.83, "Llama-3.1-8B-Instruct",                         "Prompt", "Meta",         "meta llama 3 community"),
    (86, 25.55, "MiniCPM3-4B-FC",                                "FC",     "openbmb",      "apache-2.0"),
    (87, 25.26, "Claude-Haiku-4-5-20251001",                     "Prompt", "Anthropic",    "proprietary"),
    (88, 24.97, "Amazon-Nova-Pro-v1:0",                          "FC",     "Amazon",       "proprietary"),
    (89, 24.90, "Claude-Sonnet-4-5-20250929",                    "Prompt", "Anthropic",    "proprietary"),
    (90, 24.88, "GPT-4.1-nano-2025-04-14",                       "Prompt", "OpenAI",       "proprietary"),
    (91, 24.03, "Falcon3-7B-Instruct",                           "FC",     "TII UAE",      "falcon-llm-license"),
    (92, 23.93, "Qwen3-0.6B",                                    "FC",     "Qwen",         "apache-2.0"),
    (93, 23.23, "Granite-20b-FunctionCalling",                   "FC",     "IBM",          "apache-2.0"),
    (94, 22.38, "Qwen3-0.6B",                                    "Prompt", "Qwen",         "apache-2.0"),
    (95, 22.29, "Amazon-Nova-Micro-v1:0",                        "FC",     "Amazon",       "proprietary"),
    (96, 22.25, "RZN-T",                                         "Prompt", "Phronetic AI", "apache-2.0"),
    (97, 22.08, "MiniCPM3-4B",                                   "Prompt", "openbmb",      "apache-2.0"),
    (98, 21.95, "Llama-3.2-3B-Instruct",                         "FC",     "Meta",         "meta llama 3 community"),
    (99, 21.90, "Bielik-11B-v2.3-Instruct",                      "Prompt", "SpeakLeash",   "apache-2.0"),
    (100,21.22, "Hammer2.1-0.5b",                                "FC",     "MadeAgents",   "cc-by-nc-4.0"),
    (101,19.62, "Gemma-3-4b-it",                                 "Prompt", "Google",       "gemma-terms-of-use"),
    (102,19.31, "Open-Mistral-Nemo-2407",                        "Prompt", "Mistral AI",   "proprietary"),
    (103,18.98, "Granite-4.0-350m",                              "FC",     "IBM",          "apache-2.0"),
    (104,16.25, "Falcon3-3B-Instruct",                           "FC",     "TII UAE",      "falcon-llm-license"),
    (105,11.10, "Ministral-8B-Instruct-2410",                    "FC",     "Mistral AI",   "proprietary"),
    (106,11.08, "Falcon3-1B-Instruct",                           "FC",     "TII UAE",      "falcon-llm-license"),
    (107,10.82, "Llama-3.2-1B-Instruct",                         "FC",     "Meta",         "meta llama 3 community"),
    (108,10.00, "Llama-3.1-Nemotron-Ultra-253B-v1",              "FC",     "NVIDIA",       "nvidia-open-model-license"),
    (109, 7.17, "Gemma-3-1b-it",                                 "Prompt", "Google",       "gemma-terms-of-use"),
]

# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Filtre le Berkeley Function Calling Leaderboard (BFCL) — "
                    "mesure la qualité de tool/function calling."
    )
    parser.add_argument("--keyword",   type=str,  default=None, help="Filtre sur le nom du modèle")
    parser.add_argument("--top",       type=int,  default=40,   help="Nombre max de résultats")
    parser.add_argument("--fc-only",   action="store_true",     help="FC natif uniquement (pas Prompt)")
    parser.add_argument("--open-only", action="store_true",     help="Open-source uniquement")
    parser.add_argument("--min-score", type=float, default=0.0, help="Score BFCL minimum")
    args = parser.parse_args()

    models = [
        {"rank": r, "score": s, "model": m, "mode": mo, "org": o, "license": lic}
        for r, s, m, mo, o, lic in _BFCL_DATA
    ]

    # Apply filters
    if args.fc_only:
        models = [r for r in models if r["mode"] == "FC"]
    if args.open_only:
        models = [r for r in models if r["license"] in _OPEN_LICENSES]
    if args.keyword:
        kw = args.keyword.lower()
        models = [r for r in models if kw in r["model"].lower()]
    if args.min_score:
        models = [r for r in models if r["score"] >= args.min_score]

    models = models[: args.top]

    if not models:
        print("Aucun modèle trouvé avec ces critères.")
        return

    # Print table
    col = min(max(len(r["model"]) for r in models), 45)
    col_org = min(max(len(r["org"]) for r in models), 16)
    print(f"\n{'#':>4}  {'Score':>6}  {'Modèle':<{col}}  {'Mode':<6}  {'Org':<{col_org}}  Licence")
    print("-" * (col + col_org + 38))
    for r in models:
        name = r["model"][:col]
        org  = r["org"][:col_org]
        flag = "🔓" if r["license"] in _OPEN_LICENSES else "  "
        print(f"{r['rank']:>4}  {r['score']:>6.2f}  {name:<{col}}  {r['mode']:<6}  {org:<{col_org}}  {flag} {r['license']}")

    print(f"\n{len(models)} modèles affichés  (snapshot BFCL du 12 avril 2026)")
    print("🔓 = open-source / utilisable localement (GGUF probable)")
    print("Score = overall accuracy BFCL V4 (tool calling pur)")
    print("Source : https://gorilla.cs.berkeley.edu/leaderboard.html")


if __name__ == "__main__":
    main()
