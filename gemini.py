import google.generativeai as genai
class gemini_class:
    def __init__(self):
        self.api_key="AIzaSyCslRDThpC7ZCXUSTNNZFYispZ-XNgd1f4"
        genai.configure(api_key=self.api_key)

    def process_policy(self, policy):
    
        prompt = f"""
        You are a workplace communication assistant.

        Your task is to write a **formal and professional email** to employees about a new internal policy. 
        The content of the policy is:

        \"{policy}\"

        ✅ Do:
        - Use formal tone.
        - Start with a subject.
        - Do not repeat the policy as-is; paraphrase it naturally.
        - Keep it concise and respectful.
        - Keep the sender department = Compliance Department

        ❌ Don't:
        - Add explanations or reasons.
        - Add commentary or interpretation.
        - Don't generate more than the email.
        - Strictly follow the email pattern

        Now, generate the email:
        """
            
        model = genai.GenerativeModel(model_name="models/gemini-2.0-flash")
        response = model.generate_content(prompt)
        
        # Step 5: Output result
        print(response.text)
        return response.text
