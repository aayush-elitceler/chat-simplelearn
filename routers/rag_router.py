import re
import json
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableParallel
from operator import itemgetter
from openai import OpenAI
from pymilvus import connections
from pymilvus.orm import utility
from starlette.responses import StreamingResponse

from config.settings import settings
from models.rags import PersonaChatRequest
from prompts import get_persona_rag_prompt
from repository.ai_utilities import ai_utility_repo
from repository.rags.rags_repo import rags_repo
from models.rags.rag_models import ChatRequest, CollectionSummaryRequest, CollectionSummaryResponse, \
                                    DeleteCollectionRequest, DeleteCollectionResponse
from models.rags.rag_models import ChatMessage

router = APIRouter(
    prefix="/api/v1/rag",
    tags=["RAG Operations"]
)


CURATED_TOPIC_LINKS = {
    # CBSE Biology
    "diversity in living world": [
        "https://www.youtube.com/watch?v=OIgBF5LdCd0",
    ],
    "life processes in animals": [
        "https://www.youtube.com/watch?v=gxxFGK-DTI0",
    ],
    "invisible living world": [
        "https://www.youtube.com/watch?v=cK38TmQVubk",
    ],
    # CBSE Chemistry
    "materials around us": [
        "https://www.youtube.com/watch?v=fssBfBdUJM&list=PLgnue5NFkOvVax08ucuSg_dhQamB5iUHm",
    ],
    "changes around us": [
        "https://www.youtube.com/watch?v=_FnAZxpGuZo",
    ],
    "nature of matter": [
        "https://www.youtube.com/watch?v=DTlRWVMnSYQ",
    ],
    "elements and compounds": [
        "https://www.youtube.com/watch?v=neOmNQrz88M",
    ],
    # Cambridge Grade 6-8 Physics/Chemistry topics
    "atoms": [
        "https://www.youtube.com/watch?v=jMW_0Ro6b5c",
    ],
    "atomic structures": [
        "https://www.youtube.com/watch?v=4QblYo-XeoY&list=PL3GBdsS--0-SsR0XRAhFyz7ooQkOasfyW&index=19",
    ],
    "sub atomic particles": [
        "https://www.youtube.com/watch?v=0_RQ9wb2ZPg",
    ],
    "thompson and rutherford model": [
        "https://www.youtube.com/watch?v=4Z-cWHC3Ioc",
    ],
    # Activities
    "building atomic model": [
        "https://www.youtube.com/watch?v=v48u8hjqNBU",
        "https://www.youtube.com/watch?v=SUwVYAcEkLE",
        "https://phet.colorado.edu/en/simulations/build-an-atom",
    ],
}


def _curated_links_for_question(question: str):
    if not question:
        return []
    q = question.lower()
    matched = []
    for topic, links in CURATED_TOPIC_LINKS.items():
        if topic in q:
            matched.extend(links)
    # If nothing matched, try some fuzzy contains for key tokens
    if not matched:
        token_map = {
            "diversity": "diversity in living world",
            "living world": "diversity in living world",
            "atoms": "atoms",
            "atomic structure": "atomic structures",
            "subatomic": "sub atomic particles",
            "thompson": "thompson and rutherford model",
            "rutherford": "thompson and rutherford model",
            "materials around": "materials around us",
            "changes around": "changes around us",
            "elements and compounds": "elements and compounds",
            "life processes": "life processes in animals",
        }
        for key, target in token_map.items():
            if key in q:
                matched.extend(CURATED_TOPIC_LINKS.get(target, []))
    # Deduplicate keep order
    seen = set()
    return [u for u in matched if not (u in seen or seen.add(u))]

@router.post("/asyncStreamQuery")
async def chat_with_rag_stream(
        request: ChatRequest
):
    try:
        final_question = request.question
        transcribed_text = None

        if request.is_audio:
            if not request.audio_data and not request.audio_url:
                raise HTTPException(status_code=400, detail="Audio data or URL required when is_audio=True")

            transcribed_text = await ai_utility_repo.transcribe_audio(request.audio_data, request.audio_url)
            final_question = transcribed_text

            if request.question:
                final_question = f"{request.question}\n\nAudio transcription: {transcribed_text}"

        elif not request.question:
            raise HTTPException(status_code=400, detail="Question is required when is_audio=False")

        lc_messages = [
            HumanMessage(content=msg.content) if msg.role == "user"
            else AIMessage(content=msg.content)
            for msg in request.chat_history
        ]

        chain = await rags_repo.aget_chat_chain(
            request.collection_name,
            request.chat_language or "en"
        )

        async def generate_stream():
            full_content = ""
            sources = []

            try:
                retriever = await rags_repo._aget_retriever(request.collection_name)
                retrieved_docs = await retriever.ainvoke(final_question)

                for doc in retrieved_docs:
                    doc_source = doc.metadata.get('source', '')
                    doc_page = doc.metadata.get('page', 1)
                    
                    source_key = f"{doc_source}, Page: {doc_page}"
                    source_data = {
                        "type": "source",
                        "reference": source_key
                    }
                    sources.append(source_data)
                    yield f"data: {json.dumps(source_data)}\n\n"

                chain_input = {
                    "question": final_question,
                    "chat_history": lc_messages
                }

                async for chunk in chain.astream(chain_input):
                    if hasattr(chunk, 'content') and chunk.content:
                        content = chunk.content
                        chunk_data = {
                            "type": "content",
                            "content": content,
                            "role": "assistant",
                            "collection": request.collection_name
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                        full_content += content
                    elif isinstance(chunk, dict) and 'answer' in chunk:
                        content = chunk['answer']
                        chunk_data = {
                            "type": "content",
                            "content": content,
                            "role": "assistant",
                            "collection": request.collection_name
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                        full_content += content

                # For Cambridge School textbook system, we only provide textbook-based answers
                # No external curated links are added to maintain strict textbook-only responses

                final_data = {
                    "type": "complete",
                    "role": "assistant",
                    "content": full_content,
                    "sources": sources,
                    "collection": request.collection_name,
                    "transcribed_text": transcribed_text if transcribed_text else None
                }
                yield f"data: {json.dumps(final_data)}\n\n"
                yield "data: [DONE]\n\n"

            except Exception as e:
                print(f"Error in stream generation: {str(e)}")
                error_data = {
                    "type": "error",
                    "error": str(e)
                }
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "X-Accel-Buffering": "no",
            }
        )

    except Exception as e:
        print(f"Error in chat_with_rag_stream: {str(e)}")
        raise HTTPException(500, f"Processing failed: {str(e)}")

@router.post("/asyncStreamQueryV2")
async def chat_with_rag_stream_v2(
        request: ChatRequest
):
    try:
        final_question = request.question
        transcribed_text = None

        if request.is_audio:
            if not request.audio_data and not request.audio_url:
                raise HTTPException(status_code=400, detail="Audio data or URL required when is_audio=True")

            transcribed_text = await ai_utility_repo.transcribe_audio(request.audio_data, request.audio_url)
            final_question = transcribed_text

            if request.question:
                final_question = f"{request.question}\n\nAudio transcription: {transcribed_text}"

        elif not request.question:
            raise HTTPException(status_code=400, detail="Question is required when is_audio=False")

        lc_messages = [
            HumanMessage(content=msg.content) if msg.role == "user"
            else AIMessage(content=msg.content)
            for msg in request.chat_history
        ]

        chain = await rags_repo.aget_chat_chain(
            request.collection_name,
            request.chat_language or "en"
        )

        async def generate_stream():
            full_content = ""
            sources = []

            try:
                retriever = rags_repo._get_retriever(request.collection_name)
                retrieved_docs = retriever.get_relevant_documents(final_question)

                for doc in retrieved_docs:
                    doc_source = doc.metadata.get('source', '')
                    doc_page = doc.metadata.get('page', 1)
                    
                    source_key = f"{doc_source}, Page: {doc_page}"
                    source_data = {
                        "type": "source",
                        "reference": source_key
                    }
                    sources.append(source_data)
                    yield f"data: {json.dumps(source_data)}\n\n"

                async for chunk in chain.astream({
                    "question": final_question,
                    "chat_history": lc_messages
                }):
                    if hasattr(chunk, 'content') and chunk.content:
                        chunk_data = {
                            "type": "content",
                            "content": chunk.content,
                            "role": "assistant",
                            "collection": request.collection_name
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                        full_content += chunk.content

                # For Cambridge School textbook system, we only provide textbook-based answers
                # No external curated links are added to maintain strict textbook-only responses

                final_data = {
                    "type": "complete",
                    "role": "assistant",
                    "content": full_content,
                    "sources": sources,
                    "collection": request.collection_name,
                    "transcribed_text": transcribed_text if transcribed_text else None
                }
                yield f"data: {json.dumps(final_data)}\n\n"
                yield "data: [DONE]\n\n"

            except Exception as e:
                error_data = {
                    "type": "error",
                    "error": str(e)
                }
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            }
        )

    except Exception as e:
        raise HTTPException(500, f"Processing failed: {str(e)}")

@router.post("/summarizeCollection", response_model=CollectionSummaryResponse)
async def summarize_collection(request: CollectionSummaryRequest):
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        docs = rags_repo.get_collection_documents(
            collection_name=request.collection_name,
            max_docs=request.max_docs
        )

        if not docs:
            raise HTTPException(404, f"No documents found in collection '{request.collection_name}'")

        formatted_docs = rags_repo._format_docs(docs)
        summary_prompt = f"""Create a {request.summary_length} summary of these {len(docs)} documents.
        Focus on key themes, patterns, and notable exceptions.
        Length guide:
        - Short: 1-2 paragraphs
        - Medium: 3-5 paragraphs
        - Detailed: Comprehensive analysis

        Documents:
        {formatted_docs[:15000]}
        """

        response = client.chat.completions.create(
            model=request.llm,
            messages=[{
                "role": "system",
                "content": "You are an expert document analyst. Create accurate, concise summaries."
            }, {
                "role": "user",
                "content": summary_prompt
            }],
            temperature=0.3
        )

        return CollectionSummaryResponse(
            collection=request.collection_name,
            summary=response.choices[0].message.content,
            document_count=len(docs))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Summarization failed: {str(e)}")

@router.delete("/deleteCollection", response_model=DeleteCollectionResponse)
async def delete_collection(request: DeleteCollectionRequest):
    try:
        connections.connect(
            alias="default",
            uri=settings.MILVUS_URI,
            token=settings.MILVUS_TOKEN
        )

        if not request.confirm:
            return DeleteCollectionResponse(
                success=False,
                collection_name=request.collection_name,
                message="Deletion not confirmed - set confirm=True to delete"
            )

        # Track results
        milvus_dropped = False

        # Drop Milvus collection if it exists
        if utility.has_collection(request.collection_name):
            utility.drop_collection(request.collection_name)
            milvus_dropped = True

        # Craft response message
        if milvus_dropped:
            message = "Collection successfully deleted"
        else:
            return DeleteCollectionResponse(
                success=False,
                collection_name=request.collection_name,
                message="Nothing to delete: collection not found"
            )

        return DeleteCollectionResponse(
            success=True,
            collection_name=request.collection_name,
            message=message
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Deletion failed: {str(e)}"
        )
    finally:
        connections.disconnect("default")




@router.post("/personaStreamQuery")
async def chat_with_persona_rag_stream(
        request: PersonaChatRequest
):
    try:
        persona = request.persona
        valid_personas = ["ux", "sales", "technical", "management", "default"]
        if persona.lower() not in valid_personas:
            raise HTTPException(status_code=400, detail=f"Invalid persona. Must be one of: {valid_personas}")

        final_question = request.question
        if request.is_audio and (request.audio_data or request.audio_url):
            transcribed_text = "[Audio transcription placeholder]"
            final_question = transcribed_text
            if request.question:
                final_question = f"{request.question}\n\nAudio transcription: {transcribed_text}"
        elif not request.question:
            raise HTTPException(status_code=400, detail="Question is required")

        lc_messages = [
            HumanMessage(content=msg.content) if msg.role == "user"
            else AIMessage(content=msg.content)
            for msg in request.chat_history
        ]

        retriever = rags_repo._get_retriever(request.collection_name)
        retrieved_docs = retriever.get_relevant_documents(final_question)

        context = rags_repo._format_docs(retrieved_docs)
        persona_prompt = get_persona_rag_prompt(persona, request.chat_language or "en")

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", persona_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ])

        chain = (
                RunnableParallel({
                    "context": lambda x: context,
                    "question": itemgetter("question"),
                    "chat_history": itemgetter("chat_history")
                })
                | prompt_template
                | rags_repo.llm
        )

        async def generate_stream():
            full_content = ""

            try:
                meta_data = {
                    "type": "persona_info",
                    "persona": persona,
                    "collection": request.collection_name
                }
                yield f"data: {json.dumps(meta_data)}\n\n"

                async for chunk in chain.astream({
                    "question": final_question,
                    "chat_history": lc_messages
                }):
                    if hasattr(chunk, 'content') and chunk.content:
                        chunk_data = {
                            "type": "content",
                            "content": chunk.content,
                            "role": "assistant",
                            "persona": persona
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                        full_content += chunk.content

                processed_content = full_content

                sources_section = ""
                sources = []

                sources_markers = ["SOURCES:", "REFERENCES:", "Sources:", "References:"]
                for marker in sources_markers:
                    if marker in processed_content:
                        parts = processed_content.split(marker)
                        if len(parts) > 1:
                            processed_content = parts[0].strip()
                            sources_section = parts[1].strip()
                        break

                if sources_section:
                    source_lines = [line.strip() for line in sources_section.split('\n') if line.strip()]
                    for source_line in source_lines:
                        if source_line.startswith('[') and source_line.endswith(']'):
                            source_text = source_line[1:-1]
                            if 'Source:' in source_text and 'Page:' in source_text:
                                try:
                                    source_parts = source_text.split(',')
                                    filename_part = source_parts[0].replace('Source:', '').strip()
                                    page_part = source_parts[1].replace('Page:', '').strip()

                                    for doc in retrieved_docs:
                                        doc_source = doc.metadata.get('source', '')
                                        doc_page = doc.metadata.get('page', 1)

                                        if (doc_source in filename_part or filename_part in doc_source) and str(
                                                doc_page) == page_part:
                                            sources.append({
                                                "source": doc_source,
                                                "page": doc_page,
                                                "reference": source_line
                                            })
                                            break
                                except (IndexError, ValueError):
                                    sources.append({
                                        "source": "Unknown",
                                        "page": 1,
                                        "reference": source_line
                                    })

                completion_data = {
                    "type": "complete",
                    "role": "assistant",
                    "persona": persona,
                    "collection": request.collection_name,
                    "content": processed_content,
                    "sources": sources
                }
                yield f"data: {json.dumps(completion_data)}\n\n"
                yield "data: [DONE]\n\n"

            except Exception as e:
                error_data = {"type": "error", "error": str(e)}
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Persona stream failed: {str(e)}")