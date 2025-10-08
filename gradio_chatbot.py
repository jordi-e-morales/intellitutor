"""
Chatbot de Gradio mejorado que se ejecuta independientemente.
"""
import gradio as gr
import requests
import psycopg2
from datetime import datetime

def create_chatbot_interface():
    """Crea la interfaz del chatbot con Gradio"""
    
    with gr.Blocks(
        theme=gr.themes.Soft(),
        title="Tutor Educativo - Chatbot",
        css="""
        .gradio-container {
            max-width: 1200px !important;
        }
        .chat-message {
            padding: 15px;
            margin: 10px 0;
            border-radius: 10px;
        }
        .user-message {
            background-color: #e3f2fd;
            margin-left: 20%;
        }
        .bot-message {
            background-color: #f5f5f5;
            margin-right: 20%;
        }
        """
    ) as interface:
        
        gr.Markdown("# 🎓 Tutor Educativo Virtual")
        
        with gr.Row():
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(
                    label="Conversación",
                    height=500,
                    bubble_full_width=False,
                    show_label=False
                )
                
                with gr.Row():
                    msg = gr.Textbox(
                        label="Escribe tu pregunta aquí...",
                        placeholder="Pregúntame sobre tu materia...",
                        show_label=False,
                        scale=4,
                        container=False
                    )
                    send_btn = gr.Button("Enviar", variant="primary", scale=1)
                
                clear = gr.Button("🗑️ Limpiar conversación", variant="secondary")
                
            with gr.Column(scale=1):
                gr.Markdown("### 💡 Consejos")
                gr.Markdown("""
                - Sé específico en tus preguntas
                - Menciona el tema que te interesa
                - Puedo ayudarte con:
                  - Explicaciones de conceptos
                  - Ejercicios paso a paso
                  - Recursos adicionales
                  - Preparación de exámenes
                """)
        
        # Eventos
        def respond(message, history):
            if not message.strip():
                return history, ""
            
            # Aquí iría la lógica del chatbot con IA
            # Por ahora, respuesta simple
            bot_response = f"Entiendo tu pregunta sobre: '{message}'. Esta sería mi respuesta detallada..."
            
            history.append([message, bot_response])
            return history, ""
        
        msg.submit(respond, [msg, chatbot], [chatbot, msg])
        send_btn.click(respond, [msg, chatbot], [chatbot, msg])
        clear.click(lambda: [], None, chatbot)
    
    return interface

if __name__ == "__main__":
    interface = create_chatbot_interface()
    interface.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )