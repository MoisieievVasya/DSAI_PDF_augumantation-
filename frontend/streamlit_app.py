import streamlit as st
import requests
import json

st.title("📄 PDF Generator & Evaluator")

prompt = st.text_area("Prompt", "Generate PDF for ABC Corp...")

uploaded_file = st.file_uploader("Upload PDF or Image", type=["pdf", "png", "jpg", "jpeg"])

if uploaded_file:
    st.markdown("### 📎 Uploaded File:")
    if uploaded_file.type.startswith("image/"):
        st.image(uploaded_file)
    else:
        st.write(f"📄 {uploaded_file.name}")

if st.button("Generate") and uploaded_file:
    with st.spinner("Processing..."):
        if uploaded_file.type == "application/pdf":
            files = {"pdf_files": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            data = {"prompt": prompt}
            response = requests.post(
                "http://fastapi:8000/generate-pdf",
                files=files,
                data=data
            )
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
            st.download_button(
                label="📥 Download PDF",
                data=response.content,
                file_name="generated_invoice.pdf",
                mime="application/pdf"
            )
        else:
            st.error(f"❌ Generation failed: {response.status_code}")

st.markdown("### 🧪 Evaluation JSON")
generated_json = st.text_area("Paste generated JSON here")

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