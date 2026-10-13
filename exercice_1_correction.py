import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class CodeReviewService:
    def __init__(self):
        gemini_key = os.getenv("GEMINI_API_KEY")
        self.client = OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=gemini_key,
        )

    def analyser_code(self, code_source: str) -> LLMResponse:
        system_prompt = ("Tu est un Tech lead expert en Angular"
                         "Ton role est de faire la revue du code transmis par les développeurs"
                         "1. Identifie les éventuels bugs ou mauvaise pratique"
                         "2. Propose une version corrigée et optimisée(utilisation des Signals, HttpRessource/rxjs)"
                         "3. Sois concis, pédagogique et bienveillant")
        response = self.client.chat.completions.create(
            model="gemini-3.8-flash",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Voici le code à analyser: \n\n ```{code_source}```"},
            ],
            temperature=0.2,
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens
        )


if __name__ == "__main__":
    service = CodeReviewService()
    code_a_tester = """
    @Component({
    selector: 'app-user',
    template: `<h1>{{ user.name }}</h1>`
  })
  export class UserComponent implements OnInit {
    user: any;

    constructor(private userService: UserService) {}

    ngOnInit() {
      this.userService.getUser().subscribe(data => {
        this.user = data;
      });
    }
  }
    """
    print(f"Envois du code à analyser: {code_a_tester}")
    res = service.analyser_code(code_a_tester)
    print(res.content)

