# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Conversational AI assistant for validating Colombian identity documents (Cédula de Ciudadanía / Tarjeta de Identidad) for victim compensation claims. Users upload front/back images of their ID through a WhatsApp-style chat interface; the app validates them via Google Gemini and generates a consolidated PDF.

## Commands

- `npm run dev` — Start dev server (Vite, port 3000)
- `npm run build` — Production build
- `npm run preview` — Preview production build

No test runner or linter is configured.

## Architecture

Single-page React 19 + TypeScript app built with Vite. All source files live at the project root and in three subdirectories:

- **App.tsx** — Main component. Owns all state (useState/useRef), orchestrates the document validation flow as a state machine.
- **components/** — `ChatBubble.tsx` (message display) and `InputArea.tsx` (file upload / camera).
- **services/geminiService.ts** — Calls Google Gemini (`gemini-3-pro-preview`) with Base64-encoded images/PDFs and a Spanish-language prompt. Returns structured `ValidationResult` JSON.
- **services/pdfService.ts** — Uses jsPDF to merge front+back images into a downloadable PDF.
- **utils/fileHelpers.ts** — File-to-Base64 conversion.
- **types.ts** — Shared types: `Message`, `ValidationResult`, `FlowState`, `DocumentSide`.

### Flow State Machine

```
AWAITING_FRONT_OR_PDF → ANALYZING_FIRST → (AWAITING_BACK) → ANALYZING_BACK → COMPLETED
                                                                              ↘ ERROR
```

### Key Technical Details

- **AI model**: `gemini-3-pro-preview` with 2048-token thinking budget and JSON response schema.
- **Styling**: Tailwind CSS loaded via CDN (no build step for CSS). WhatsApp-inspired green theme (#008069, #00a884).
- **All UI text is in Spanish** — the target audience is rural Colombian victims; keep language simple.
- **No routing** — single-view app.
- **No external state management** — plain React hooks.
- **Path alias**: `@/*` maps to project root (configured in vite.config.ts and tsconfig.json).

## Environment Variables

Set `GEMINI_API_KEY` in `.env.local` (git-ignored). Vite exposes it as `process.env.GEMINI_API_KEY` via `define` in vite.config.ts.
