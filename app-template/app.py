import asyncio

from h2o_wave import app, Q, ui, on, handle_on, data, copy_expando, main
from h2ogpte import H2OGPTE
from loguru import logger
import json

rag_url = 'https://h2ogpte.genai-training.h2o.ai'
rag_key = None
NAME = 'John Doe'
TITLE = 'Senior Analyst'
SYSTEM_PROMPT = "Hello, I'm an AI bot with access to your LinkedIn profile. How can I assist you today? Whether " \
                "it's updating your professional summary, connecting with new contacts, job search advice, " \
                "or anything related to your career, I'm here to help. Just let me know what you need, and " \
                "I'll provide personalized assistance based on your LinkedIn information."
COLLECTION_NAME = "MyProfile"

@app('/')
async def serve(q: Q):
    copy_expando(q.args, q.client)

    # First time a browser comes to the app
    if not q.client.initialized:
        await init(q)
        q.client.initialized = True

    # Other browser interactions
    elif not await handle_on(q):
        q.page["my_card"] = {}
    await q.page.save()

async def init(q: Q) -> None:
    q.page['meta'] = ui.meta_card(
        box='',
        title='AI Enhanced Career Development',
        theme='lighting',
        layouts=[
            ui.layout(
                breakpoint='s',
                min_height='100vh',
                max_width='1200px',
                zones=[
                    ui.zone('header'),
                    ui.zone('content', size='0', zones=[
                        ui.zone('vertical', size='1', ),
                        ui.zone('collection_zone', size='1', direction=ui.ZoneDirection.ROW),
                        ui.zone('horizontal', size='1', direction=ui.ZoneDirection.ROW),
                        ui.zone('grid', direction=ui.ZoneDirection.ROW, wrap='stretch', justify='center')
                    ]),
                    ui.zone(name='footer'),
                ]
            )
        ]
    )
    q.page['header'] = ui.header_card(
        box='header',
        title='Personal AI Assistant',
        subtitle="",
        image='https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRYiPLBie36OVSxyLYJAFQrykIDPkkft-0cBA&usqp=CAU',
        items=[ui.persona(title=NAME, subtitle=TITLE, caption='Online', size='m',
                          image='https://images.pexels.com/photos/220453/pexels-photo-220453.jpeg?auto=compress&h=750&w=1260')]
    )
    q.page['footer'] = ui.footer_card(
        box='footer',
        caption='Made with love using [H2O Wave](https://wave.h2o.ai).'
    )
    await home(q)

@on()
async def home(q: Q):
    q.page['image'] = ui.tall_info_card(
        box=ui.box('vertical', size='0'), title='', name='image_card',
        caption='Personal AI Assistant',
        image_height='600px',
        image='https://images.pexels.com/photos/8386440/pexels-photo-8386440.jpeg')
    
    q.page['find_collection'] = ui.form_card(box=ui.box('collection_zone', size='1'),
        items=[ui.inline(items=[
            ui.textbox(name="api_key", width="90%", value=rag_key, placeholder="Paste your API key here!"),
            ui.button(name="launch", label="Launch", primary=True, width="10%")])])

@on()
async def launch(q):
    # Log into RAG system
    h2ogpte = H2OGPTE(address=rag_url, api_key=q.args.api_key)
    q.client.h2ogpte = h2ogpte
    collections = h2ogpte.list_recent_collections(0, 1000)
    collection_id = [i.id for i in collections if i.name == COLLECTION_NAME][0]
    
    # ask h2ogpte for your name
    NAME = h2ogpte.answer_question("What is this person's name?")
    
    # Inspect and collect all text chunks
    chunks = []
    for chunk_id in range(1, 100):  # TODO: get number of chunks from collection
        try:
            chunk = h2ogpte.get_chunks(collection_id, [chunk_id])
            chunks.append(chunk[0].text)
        except:
            break

    print(f"Number of chunks: {len(chunks)}", flush=True)

    
    try:
        extracted_name = h2ogpte.extract_data(
            text_context_list=chunks,
            system_prompt = 'You are a helpful AI Assistant and your goal is to extract names',
            prompt_extract= "Return only the name of the person this profile belongs to as a JSON"
        )

        name_json = json.loads(extracted_name.content[0])
        NAME = name_json['name']
        
        extracted_title = h2ogpte.extract_data(
            text_context_list=chunks,
            system_prompt = 'You are a helpful AI Assistant and your goal is to extract professional titles',
            prompt_extract= "Return only the current position title of the person this profile belongs to as a JSON with a single field called title"
        )

        title_json = json.loads(extracted_title.content[0])
        TITLE = title_json['title']
    except:
        NAME = 'John Doe'
        TITLE = 'Senior Analyst'
    
    q.page['header'] = ui.header_card(
        box='header',
        title='Personal AI Assistant',
        subtitle="",
        image='https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRYiPLBie36OVSxyLYJAFQrykIDPkkft-0cBA&usqp=CAU',
        items=[ui.persona(title=NAME, subtitle=TITLE, caption='Online', size='m',
                          image='https://images.pexels.com/photos/220453/pexels-photo-220453.jpeg?auto=compress&h=750&w=1260')]
    )
    
    # Start chat session
    q.client.chat_session_id = h2ogpte.create_chat_session(collection_id)
    q.page['chatbot'] = ui.chatbot_card(box='horizontal',
                            data=data('content from_user', t='list',
                             rows=[["Welcome! What would you like to accomplish today using **{}**?".format(COLLECTION_NAME), False]], ),
                            name='chatbot_name')

@on()
async def chatbot_name(q: Q):
    """Answer the question"""
    question = q.args.chatbot_name
    q.page["chatbot"].data += [question, True]
    await q.page.save()
    q.page["chatbot"].data += ["<img src='{}' height='40px'/>".format('https://i.gifer.com/9u7v.gif'), False]
    await q.page.save()
    output = await q.run(get_chat_answer, q.client.h2ogpte, q.client.chat_session_id, question)
    await q.page.save()
    stream = ""
    final_output = f"""{output} <br/>"""
    # remove the last line
    q.page['chatbot'].data[-1] = [stream, False]
    for w in final_output.split('/n'):
        await asyncio.sleep(0.3)
        stream += w + " "
        q.page["chatbot"].data[-1] = [stream, False]
        await q.page.save()

def get_chat_answer(h2ogpte, chat_session_id, question):
    with h2ogpte.connect(chat_session_id) as session:
        reply = session.query(question, timeout=10600,
            system_prompt="Hello, I'm an AI bot with access to your LinkedIn profile. How can I assist you today? Whether it's updating your professional summary, connecting with new contacts, job search advice, or anything related to your career, I'm here to help. Just let me know what you need, and I'll provide personalized assistance based on your LinkedIn information")
        answer = reply.content
    return answer
