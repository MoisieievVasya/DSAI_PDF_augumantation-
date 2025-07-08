import streamlit as st
import base64
import requests
import json
import matplotlib.pyplot as plt
import pandas as pd

def show_pdf(pdf_data):
    base64_pdf = base64.b64encode(pdf_data).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

st.title("📄 PDF Generator")

prompt = st.text_area("Prompt", "Generate invoice")

uploaded_file = st.file_uploader("Upload PDF or Image", type=["pdf", "png", "jpg", "jpeg"])

if st.button("Generate") and uploaded_file:
    with st.spinner("Processing..."):
        if uploaded_file.type == "application/pdf":
            files = {"pdf_files": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        else:
            files = {"images": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        data = {"prompt": prompt}
        response = requests.post(
            "http://fastapi:8000/generate-pdf",
            files=files,
            data=data
        )

        if response.status_code == 200:
            st.success("✅ PDF generated!")
            show_pdf(response.content)
            st.download_button(
                label="📥 Download PDF",
                data=response.content,
                file_name="generated_invoice.pdf",
                mime="application/pdf"
            )

            # Try to load JSON if available
            try:
                response_json = requests.get("http://fastapi:8000/generated_invoice.pdf.json")
                if response_json.status_code == 200:
                    st.session_state["generated_json"] = json.dumps(response_json.json(), indent=2)
            except:
                pass
        else:
            st.error(f"❌ Generation failed: {response.status_code}")

if st.button("Evaluate"):
    try:
        eval_response = requests.post("http://fastapi:8000/evaluate")

        if eval_response.status_code == 200:
            result = eval_response.json()
            table = result["table"]
            metrics = result["metrics"]

            st.dataframe(pd.DataFrame(table))

            st.markdown("### 📊 Evaluation Metrics")

            # Semantic Quality
            st.markdown("📌 **Semantic Quality:**")
            st.markdown(f"- Avg Semantic Similarity: {metrics.get('avg_semantic_similarity', 'N/A')}")
            st.markdown(f"- Avg All Similarity: {metrics.get('avg_all_similarity', 'N/A')}")
            st.markdown(f"- Document Coherence: {metrics.get('document_coherence', 'N/A')}")

            # Diversity (Distinct)
            st.markdown("📌 **Diversity (Distinct):**")
            st.markdown(f"- Distinct-1: {metrics.get('distinct-1', 'N/A')}")
            st.markdown(f"- Distinct-2: {metrics.get('distinct-2', 'N/A')}")
            st.markdown(f"- Distinct-3: {metrics.get('distinct-3', 'N/A')}")

            # Issues
            st.markdown("📌 **Issues:**")
            st.markdown(f"- Low Similarity Fields: {metrics.get('low_similarity_fields', 'N/A')}")
            st.markdown(f"- Invalid Format Fields: {metrics.get('invalid_format_fields', 'N/A')}")

        else:
            st.error(f"Evaluation failed: {eval_response.status_code}")
    except Exception as e:
        st.error(f"Invalid JSON: {e}")
