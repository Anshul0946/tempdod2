import streamlit as st
import tempfile
import os
import time
from pathlib import Path
from core.config import ProcessingContext
from core.pipeline import Pipeline
from core.constants import REASONING_MODEL_DEFAULT

class StreamlitLogger:
    """Custom logger that writes to both context and a live display."""
    def __init__(self, context: ProcessingContext, log_placeholder):
        self.context = context
        self.placeholder = log_placeholder
        
    def log(self, message: str):
        self.context.log(message)
        # Update display immediately
        self.placeholder.text_area(
            "Live Logs", 
            value="\n".join(self.context.logs[-50:]),  # Show last 50 logs
            height=300,
            key=f"log_{len(self.context.logs)}"
        )


def main():
    st.set_page_config(page_title="Cellular Processor", layout="wide")
    st.title("🔬 5G DOD Processor (Refactored)")
    st.caption("PaddleOCR + DeepSeek-v3 Pipeline")

    # Session State
    if "context" not in st.session_state:
        st.session_state.context = ProcessingContext()
    
    # Sidebar
    st.sidebar.header("🔑 API Key")
    token = st.sidebar.text_input("NVIDIA API Key", type="password")
    
    if token and len(token) > 20:
        st.session_state.api_valid = True
        st.session_state.token = token
        st.sidebar.success("✅ Valid Key")
    else:
        st.session_state.api_valid = False
        if token:
            st.sidebar.error("❌ Invalid Key")

    if st.sidebar.button("🔄 Reset"):
        st.session_state.context = ProcessingContext()
        st.rerun()

    # Main Area
    if st.session_state.get("api_valid"):
        uploaded = st.file_uploader("📁 Upload Excel Template", type=["xlsx"])
        
        reasoning_model = st.text_input("Reasoning Model", value=REASONING_MODEL_DEFAULT)

        if uploaded:
            if st.button("🚀 Process", type="primary"):
                # Setup
                temp_dir = tempfile.mkdtemp()
                file_path = os.path.join(temp_dir, uploaded.name)
                with open(file_path, "wb") as f:
                    f.write(uploaded.getbuffer())

                # Create context
                ctx = ProcessingContext()
                st.session_state.context = ctx
                ctx.temp_dir = temp_dir
                
                # Setup Logger and Pipeline
                log_placeholder = st.empty()
                logger = StreamlitLogger(ctx, log_placeholder)
                
                # Hijack context.log to write to UI
                # We need to monkeypath the instance method for this run
                original_log = ctx.log
                def ui_logging_wrapper(msg):
                    original_log(msg)
                    logger.log(msg) # Re-calls context.log internally but also updates UI
                
                # Actually, simpler: just use a lambda that calls both
                ctx.log = lambda msg: logger.log(msg) # Overwrite instance method

                pipeline = Pipeline(ctx, st.session_state.token)
                
                # Progress display
                progress = st.progress(0, text="Starting...")
                
                try:
                    ctx.log("Starting processing pipeline...")
                    progress.progress(10, text="Pipeline Running...")
                    
                    # Run workflow
                    result_path = pipeline.run(file_path, reasoning_model)
                    
                    progress.progress(100, text="Complete!")
                    
                    if result_path and os.path.exists(result_path):
                        st.success("✅ Done! Download your processed file below.")
                        
                        # Read file for download
                        with open(result_path, "rb") as f:
                            file_data = f.read()
                            
                        st.download_button(
                            "📥 Download Results", 
                            file_data, 
                            file_name=f"processed_{uploaded.name}",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                except Exception as e:
                    st.error(f"❌ Error: {e}")
                    ctx.log(f"CRITICAL ERROR: {e}")
                    import traceback
                    ctx.log(traceback.format_exc())

    # Always show logs
    st.markdown("---")
    st.subheader("📋 Logs")
    
    logs = st.session_state.context.logs
    if logs:
        st.text_area("Processing Logs", value="\n".join(logs), height=400)
        st.caption(f"{len(logs)} entries")
    else:
        st.info("Upload a file and click Process to see logs")

if __name__ == "__main__":
    main()
