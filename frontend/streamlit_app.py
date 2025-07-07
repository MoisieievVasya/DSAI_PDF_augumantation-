import streamlit as st
import base64
import requests
import json
import os

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

# Pre-populate text area
generated_json = st.text_area("Paste generated JSON here", value=st.session_state.get("generated_json", ""))

if st.button("Evaluate") and generated_json:
    try:
        parsed_json = json.loads(generated_json)
        eval_response = requests.post("http://fastapi:8000/evaluate", json=parsed_json)

        if eval_response.status_code == 200:
            result = eval_response.json()
            table = result["table"]
            metrics = result["metrics"]

            st.dataframe(table)

            if st.button("Show Evaluation Metrics"):
                st.json(metrics)

        else:
            st.error(f"Evaluation failed: {eval_response.status_code}")
    except Exception as e:
        st.error(f"Invalid JSON: {e}")
