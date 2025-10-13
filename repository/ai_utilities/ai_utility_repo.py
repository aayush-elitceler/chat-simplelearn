import base64
import requests
from repository.rags import rags_repo
import asyncio
from typing import Dict, Any, List
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from config.settings import settings
from openai import OpenAI
import io
import json


class AiUtilityRepo:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo-16k",
            temperature=0,
            api_key=settings.OPENAI_API_KEY,
        )
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

    async def generate_collection_insights(self, collection_name: str) -> Dict[str, Any]:
        try:
            all_docs = rags_repo.get_collection_documents(collection_name, max_docs=100)
            if not all_docs:
                return {
                    "summary": "No documents found in collection",
                    "important_stats": "No documents found in collection",
                    "missing_info": "No documents found in collection"
                }

            formatted_docs = rags_repo._format_docs(all_docs)

            summary_prompt = PromptTemplate.from_template("""
            Based on the following documents from the collection, provide a concise 3-line summary:

            {documents}

            Summary:
            """)

            stats_prompt = PromptTemplate.from_template("""
            Analyze the following documents and extract the most important statistics, numbers, 
            or quantitative data. Focus on key metrics, figures, and measurable information.
            If no statistics are found, mention that.

            {documents}

            Important Statistics:
            """)

            missing_prompt = PromptTemplate.from_template("""
            Analyze the following collection of documents and identify what types of information 
            or topics seem to be missing or underrepresented. Consider:
            - Time periods not covered
            - Key topics that should be included but aren't
            - Data gaps or incomplete information
            - Areas that need more documentation

            {documents}

            Missing Information:
            """)

            tasks = [
                self.llm.ainvoke(summary_prompt.format(documents=formatted_docs)),
                self.llm.ainvoke(stats_prompt.format(documents=formatted_docs)),
                self.llm.ainvoke(missing_prompt.format(documents=formatted_docs))
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            return {
                "summary": str(results[0].content) if not isinstance(results[0],
                                                                     Exception) else "Error generating summary",
                "important_stats": str(results[1].content) if not isinstance(results[1],
                                                                             Exception) else "Error extracting statistics",
                "missing_info": str(results[2].content) if not isinstance(results[2],
                                                                          Exception) else "Error identifying missing information"
            }

        except Exception as e:
            print(f"Error generating insights for collection {collection_name}: {str(e)}")
            return {
                "summary": f"Error: {str(e)}",
                "important_stats": f"Error: {str(e)}",
                "missing_info": f"Error: {str(e)}"
            }

    def _format_docs_with_budget(self, documents: List, total_char_budget: int = 14000, per_doc_limit: int = 350, max_docs: int = 120) -> str:
        parts: List[str] = []
        remaining = total_char_budget
        count = 0
        for i, doc in enumerate(documents):
            if count >= max_docs or remaining <= 0:
                break
            # Extract metadata safely
            try:
                source = getattr(doc, 'metadata', {}).get('source', 'Unknown')
                page = getattr(doc, 'metadata', {}).get('page', 1)
                gcp_url = getattr(doc, 'metadata', {}).get('gcp_url', None)
                content = getattr(doc, 'page_content', '') or ''
            except Exception:
                continue

            snippet = content[:per_doc_limit]
            block = (
                f"Document {i + 1}:\n"
                f"Source: {source}\n"
                f"Page: {page}\n"
                f"GCP URL: {gcp_url or 'Not available'}\n"
                f"Content: {snippet}\n---\n"
            )
            if len(block) > remaining:
                break
            parts.append(block)
            remaining -= len(block)
            count += 1
        return "\n".join(parts)

    async def generate_insights_from_documents(self, documents: List) -> Dict[str, Any]:
        try:
            if not documents:
                return {
                    "summary": "No documents provided",
                    "faq": [],
                }

            # Build a budgeted formatted docs string to avoid token limits
            formatted_docs = self._format_docs_with_budget(documents, total_char_budget=14000, per_doc_limit=350, max_docs=120)
            if not formatted_docs:
                # Fallback: try with even smaller budget
                formatted_docs = self._format_docs_with_budget(documents, total_char_budget=4000, per_doc_limit=200, max_docs=60)

            summary_prompt = PromptTemplate.from_template("""
            You will be given a set of document snippets.
            Write a concise, neutral, factual summary in 3-5 sentences.

            {documents}

            Summary:
            """)

            faq_prompt = PromptTemplate.from_template("""
            You will be given a set of document snippets.
            Derive 5-12 concise FAQ items that help a user understand the material.
            Return ONLY a valid JSON array of objects. Each object must have exactly two keys:
            "question" and "answer" (both strings). Do not include any other keys or any text
            before or after the JSON.

            {documents}

            JSON Array:
            """)

            tasks = [
                self.llm.ainvoke(summary_prompt.format(documents=formatted_docs)),
                self.llm.ainvoke(faq_prompt.format(documents=formatted_docs))
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Summary handling with fallback retry on failure
            if isinstance(results[0], Exception):
                print(f"Summary generation error: {results[0]}")
                # Retry with smaller budget
                smaller = self._format_docs_with_budget(documents, total_char_budget=4000, per_doc_limit=200, max_docs=60)
                retry = await self.llm.ainvoke(summary_prompt.format(documents=smaller))
                summary_text = str(getattr(retry, 'content', '')) or "Summary unavailable"
            else:
                summary_text = str(results[0].content)

            # FAQ JSON parsing with robust cleanup and fallback
            def _clean_code_fences(s: str) -> str:
                s = s.strip()
                if s.startswith("```"):
                    # remove first fence line
                    first_newline = s.find("\n")
                    if first_newline != -1:
                        s = s[first_newline + 1 :]
                    # remove trailing fence
                    if s.endswith("```"):
                        s = s[:-3]
                # remove leading json label if present
                if s.lower().startswith("json"):
                    s = s[4:].lstrip()
                return s.strip()

            faq_raw: str
            if isinstance(results[1], Exception):
                print(f"FAQ generation error: {results[1]}")
                # Retry with smaller budget
                smaller = self._format_docs_with_budget(documents, total_char_budget=4000, per_doc_limit=200, max_docs=60)
                retry_faq = await self.llm.ainvoke(faq_prompt.format(documents=smaller))
                faq_raw = str(getattr(retry_faq, 'content', '[]'))
            else:
                faq_raw = str(results[1].content)

            faq_items: List[Dict[str, str]] = []
            try:
                cleaned = _clean_code_fences(faq_raw)
                faq_items = json.loads(cleaned)
                if not isinstance(faq_items, list):
                    raise ValueError("FAQ not a list")
                # Normalize each item to required keys
                normalized = []
                for item in faq_items:
                    if isinstance(item, dict):
                        q = str(item.get("question", "")).strip()
                        a = str(item.get("answer", "")).strip()
                        if q or a:
                            normalized.append({"question": q, "answer": a})
                    elif isinstance(item, str):
                        normalized.append({"question": item[:80], "answer": item})
                faq_items = normalized
            except Exception:
                # Fallback: build simple QA pairs from lines
                lines = [ln.strip("- • \t ") for ln in faq_raw.splitlines() if ln.strip()]
                for ln in lines[:10]:
                    faq_items.append({"question": ln[:80], "answer": ln})

            return {
                "summary": summary_text,
                "faq": faq_items,
            }
        except Exception as e:
            print(f"Error generating insights from provided documents: {str(e)}")
            return {
                "summary": f"Error: {str(e)}",
                "faq": [],
            }

    async def generate_session_name(self, question: str, project_name: str = None) -> str:
        """
        Generate a 3-4 word session name based on the user's question and project context.
        """
        try:
            session_name_prompt = PromptTemplate.from_template("""
            Generate a short, descriptive session name (3-4 words maximum) based on the user's question or chat history, whicever provided.
            The name should be concise, relevant, and give a quick understanding of what the conversation is about.
            
            User Question: {question}
            Project Context: {project_context}
            
            Session Name (3-4 words only):
            """)
            
            project_context = project_name or "General conversation"
            
            response = await self.llm.ainvoke(
                session_name_prompt.format(
                    question=question,
                    project_context=project_context
                )
            )
            
            session_name = str(response.content).strip()
            session_name = session_name.strip('"\'')

            if len(session_name) > 50:
                session_name = session_name[:47] + "..."
            
            return session_name if session_name else "New Chat Session"
            
        except Exception as e:
            print(f"Error generating session name: {str(e)}")
            return "New Chat Session"

    async def transcribe_audio(self, audio_data: str = None, audio_url: str = None, audio_bytes: bytes = None) -> str:
        try:
            if audio_bytes:
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = "audio.webm"

                transcription = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
                return transcription

            elif audio_data:
                audio_bytes = base64.b64decode(audio_data.split(',')[1] if ',' in audio_data else audio_data)
                return await self.transcribe_audio(audio_bytes=audio_bytes)

            elif audio_url:
                response = requests.get(audio_url)
                response.raise_for_status()
                return await self.transcribe_audio(audio_bytes=response.content)

            else:
                raise ValueError("No audio data, bytes, or URL provided")

        except Exception as e:
            raise Exception(f"Audio transcription failed: {str(e)}")


ai_utility_repo = AiUtilityRepo()