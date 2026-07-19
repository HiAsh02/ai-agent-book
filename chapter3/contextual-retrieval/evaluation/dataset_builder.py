"""Build evaluation dataset from Chinese legal documents"""

import json
import logging
from typing import List, Dict, Any
from pathlib import Path


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LegalDatasetBuilder:
    """Build evaluation dataset for Chinese legal Q&A"""
    
    def __init__(self):
        self.simple_cases = []
        self.complex_cases = []
        
    def create_simple_cases(self) -> List[Dict[str, Any]]:
        """Create simple direct legal questions"""
        simple_cases = [
            {
                "id": "simple_1",
                "question": "How many years for intentional homicide?",
                "expected_keywords": ["Death penalty", "Life imprisonment", "Fixed-term imprisonment of not less than ten years"],
                "reference": "Article 232 of the Criminal Law of the People's Republic of China",
                "difficulty": "easy"
            },
            {
                "id": "simple_2",
                "question": "What is the filing standard for theft?",
                "expected_keywords": ["One thousand yuan", "Three thousand yuan", "Relatively large amount"],
                "reference": "Article 264 of the Criminal Law of the People's Republic of China",
                "difficulty": "easy"
            },
            {
                "id": "simple_3", 
                "question": "How is drunk driving punished?",
                "expected_keywords": ["Criminal detention", "Fine", "License revocation"],
                "reference": "Article 133 of the Criminal Law of the People's Republic of China",
                "difficulty": "easy"
            },
            {
                "id": "simple_4",
                "question": "What is the sentencing standard for fraud?",
                "expected_keywords": ["Less than three years", "Three to ten years", "More than ten years"],
                "reference": "Article 266 of the Criminal Law of the People's Republic of China",
                "difficulty": "easy"
            },
            {
                "id": "simple_5",
                "question": "What is the punishment for causing serious injury by intentional injury?",
                "expected_keywords": ["Three to ten years", "Fixed-term imprisonment"],
                "reference": "Article 234 of the Criminal Law of the People's Republic of China",
                "difficulty": "easy"
            },
            {
                "id": "simple_6",
                "question": "What are the aggravating circumstances for robbery?",
                "expected_keywords": ["Home invasion robbery", "Multiple robberies", "Robbery of a huge amount"],
                "reference": "Article 263 of the Criminal Law of the People's Republic of China",
                "difficulty": "medium"
            },
            {
                "id": "simple_7",
                "question": "What are the constitutive elements of the crime of illegal detention?",
                "expected_keywords": ["Illegal", "unlawful detention", "restriction of personal freedom"],
                "reference": "Article 238 of the Criminal Law of the People's Republic of China",
                "difficulty": "medium"
            },
            {
                "id": "simple_8",
                "question": "How is the amount standard for the crime of embezzlement determined?",
                "expected_keywords": ["30,000 yuan", "200,000 yuan", "3,000,000 yuan"],
                "reference": "Article 383 of the Criminal Law of the People's Republic of China",
                "difficulty": "medium"
            },
            {
                "id": "simple_9",
                "question": "What are the filing standards for the crime of causing traffic casualties?",
                "expected_keywords": ["causing one death", "causing three serious injuries", "property loss"],
                "reference": "Article 133 of the Criminal Law of the People's Republic of China",
                "difficulty": "easy"
            },
            {
                "id": "simple_10",
                "question": "How is the crime of picking quarrels and provoking trouble punished?",
                "expected_keywords": ["up to five years", "Fixed-term imprisonment", "Criminal detention", "public surveillance"],
                "reference": "Article 293 of the Criminal Law of the People's Republic of China",
                "difficulty": "easy"
            }
        ]
        
        return simple_cases
    
    def create_complex_cases(self) -> List[Dict[str, Any]]:
        """Create complex legal scenario questions"""
        complex_cases = [
            {
                "id": "complex_1",
                "question": """Zhang, due to an economic dispute with Li, broke into Li's home with a knife to collect a debt. During the altercation, Zhang stabbed Li with the knife, causing serious injury. Additionally, Zhang took 50,000 yuan in cash from Li's home. How should Zhang's actions be characterized? What criminal penalties might he face?""",
                "expected_analysis": ["Home invasion robbery", "intentional injury", "combined punishment for multiple crimes"],
                "reference": "Articles 234 and 263 of the Criminal Law",
                "difficulty": "hard",
                "requires_multi_query": True
            },
            {
                "id": "complex_2",
                "question": """Wang, the financial director of a state-owned enterprise, used his position to transfer 2,000,000 yuan of company funds into his controlled account through means such as issuing false invoices. Wang then used the funds for stock investments, making a profit of 500,000 yuan. After the case was discovered, Wang voluntarily returned all the illicit funds. Analyze Wang's legal liability.""",
                "expected_analysis": ["crime of embezzlement", "crime of misappropriation of public funds", "voluntary surrender", "return of illicit gains"],
                "reference": "Articles 382 and 384 of the Criminal Law",
                "difficulty": "hard",
                "requires_multi_query": True
            },
            {
                "id": "complex_3",
                "question": """Zhao, driving under the influence of alcohol, was speeding in the urban area and hit pedestrian Chen who was crossing the road, causing Chen's immediate death. Zhao then fled the scene. The next day, persuaded by his family, Zhao surrendered to the public security authorities. What crimes is Zhao suspected of? What factors should be considered in sentencing?""",
                "expected_analysis": ["crime of causing traffic casualties", "crime of dangerous driving", "hit-and-run", "Surrender"],
                "reference": "Article 133 of the Criminal Law",
                "difficulty": "hard",
                "requires_multi_query": True
            },
            {
                "id": "complex_4",
                "question": """Liu, through an online platform, released false investment information claiming guaranteed high returns, and defrauded 30 investors of a total of 5 million yuan. Among this, Liu used 2 million yuan for personal squandering and 3 million yuan to repay previous debts. How should Liu's conduct be characterized? What is the possible sentencing?""",
                "expected_analysis": ["Fraud", "Extremely large amount", "Multiple victims"],
                "reference": "Article 266 of the Criminal Law",
                "difficulty": "hard",
                "requires_multi_query": True
            },
            {
                "id": "complex_5",
                "question": """Sun and Qian conspired to steal from a shopping mall. Sun was responsible for lookout, while Qian entered the mall to commit theft. During the theft, Qian was discovered by a security guard and, in order to escape, inflicted minor injuries on the guard. Ultimately, the two stole property worth 80,000 yuan. Please analyze the respective criminal liabilities of Sun and Qian.""",
                "expected_analysis": ["Joint crime", "Theft", "Robbery", "Transformed offense"],
                "reference": "Articles 264 and 269 of the Criminal Law",
                "difficulty": "hard",
                "requires_multi_query": True
            }
        ]
        
        return complex_cases
    
    def build_dataset(self, output_path: str = "legal_qa_dataset.json"):
        """Build and save the complete dataset"""
        dataset = {
            "simple_cases": self.create_simple_cases(),
            "complex_cases": self.create_complex_cases(),
            "metadata": {
                "total_cases": 15,
                "simple_count": 10,
                "complex_count": 5,
                "domain": "Chinese Criminal Law",
                "purpose": "Evaluate agentic vs non-agentic RAG performance"
            }
        }
        
        # Save dataset
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Dataset saved to {output_path}")
        return dataset


def create_legal_documents() -> List[Dict[str, str]]:
    """Create sample legal documents for the knowledge base"""
    documents = [
        {
            "doc_id": "criminal_law_homicide",
            "title": "Criminal Law - Intentional Homicide",
            "content": """Article 232 [Intentional Homicide] Whoever intentionally commits homicide shall be sentenced to death, life imprisonment, or fixed-term imprisonment of not less than ten years; if the circumstances are relatively minor, the sentence shall be fixed-term imprisonment of not less than three years but not more than ten years.

Intentional homicide refers to the intentional and unlawful deprivation of another person's life. The object of this crime is the victim's right to life. The legal basis is Article 232 of the Criminal Law of the People's Republic of China.

Sentencing standards:
1. Serious circumstances: death penalty, life imprisonment, or fixed-term imprisonment of not less than ten years
2. Relatively minor circumstances: fixed-term imprisonment of not less than three years but not more than ten years

Relatively minor circumstances typically include: excessive defense, righteous indignation killing, victim fault, etc."""
        },
        {
            "doc_id": "criminal_law_theft",
            "title": "Criminal Law - Theft",
            "content": """Article 264 [Theft] Whoever steals public or private property in a relatively large amount, or commits theft multiple times, home invasion theft, theft with a weapon, or pickpocketing, shall be sentenced to fixed-term imprisonment of not more than three years, criminal detention, or public surveillance, and shall also, or shall only, be fined; if the amount is huge or there are other serious circumstances, the sentence shall be fixed-term imprisonment of not less than three years but not more than ten years, and a fine shall also be imposed; if the amount is especially huge or there are other especially serious circumstances, the sentence shall be fixed-term imprisonment of not less than ten years or life imprisonment, and a fine or confiscation of property shall also be imposed.

Filing standards for theft:
1. Relatively large amount: generally 1,000 yuan to 3,000 yuan or more
2. Huge amount: generally 30,000 yuan to 100,000 yuan or more
3. Especially huge amount: generally 300,000 yuan to 500,000 yuan or more

Special circumstances: multiple thefts (three or more times within two years), home invasion theft, theft with a weapon, pickpocketing, regardless of the amount, constitute theft."""
        },
        {
            "doc_id": "criminal_law_fraud",
            "title": "Criminal Law - Fraud",
            "content": """Article 266 [Fraud] Whoever defrauds public or private property in a relatively large amount shall be sentenced to fixed-term imprisonment of not more than three years, criminal detention, or public surveillance, and shall also, or shall only, be fined; if the amount is huge or there are other serious circumstances, the sentence shall be fixed-term imprisonment of not less than three years but not more than ten years, and a fine shall also be imposed; if the amount is especially huge or there are other especially serious circumstances, the sentence shall be fixed-term imprisonment of not less than ten years or life imprisonment, and a fine or confiscation of property shall also be imposed.

Sentencing standards for fraud:
1. Relatively large amount (3,000 yuan to 10,000 yuan or more): fixed-term imprisonment of not more than three years, criminal detention, or public surveillance
2. Huge amount (30,000 yuan to 100,000 yuan or more): fixed-term imprisonment of not less than three years but not more than ten years
3. Especially huge amount (500,000 yuan or more): fixed-term imprisonment of not less than ten years or life imprisonment

Fraud refers to the act of using fabricated facts or concealing the truth to defraud public or private property in a relatively large amount, with the intent of illegal possession."""
        },
        {
            "doc_id": "criminal_law_robbery",
            "title": "Criminal Law - Robbery",
            "content": """Article 263 [Robbery] Whoever robs public or private property by violence, coercion, or other methods shall be sentenced to fixed-term imprisonment of not less than three years but not more than ten years, and shall also be fined; under any of the following circumstances, the sentence shall be fixed-term imprisonment of not less than ten years, life imprisonment, or death, and a fine or confiscation of property shall also be imposed:

(1) Home invasion robbery;
(2) Robbery on public transportation;
(3) Robbery of a bank or other financial institution;
(4) Multiple robberies or robbery involving a huge amount;
(5) Robbery causing serious injury or death;
(6) Robbery by impersonating military or police personnel;
(7) Armed robbery;
(8) Robbery of military supplies or materials for emergency rescue, disaster relief, or relief.

Aggravated circumstances for robbery include the above eight situations; if any of them is present, the minimum sentence is ten years of fixed-term imprisonment."""
        },
        {
            "doc_id": "criminal_law_injury",
            "title": "Criminal Law - Intentional Injury",
            "content": """Article 234 [Intentional Injury] Whoever intentionally injures the body of another person shall be sentenced to fixed-term imprisonment of not more than three years, criminal detention, or public surveillance. Whoever commits the crime in the preceding paragraph and causes serious injury shall be sentenced to fixed-term imprisonment of not less than three years but not more than ten years; whoever causes death or causes serious injury by particularly cruel means resulting in severe disability shall be sentenced to fixed-term imprisonment of not less than ten years, life imprisonment, or death.

Sentencing for intentional injury:
1. Intentional injury causing minor injury: fixed-term imprisonment of not more than three years, criminal detention, or public surveillance
2. Intentional injury causing serious injury: fixed-term imprisonment of not less than three years but not more than ten years
3. Intentional injury causing death or causing disability by particularly cruel means: fixed-term imprisonment of not less than ten years, life imprisonment, or death

Standard for serious injury: causing limb disability or facial disfigurement; causing loss of hearing, vision, or function of other organs; other major harm to personal health."""
        },
        {
            "doc_id": "criminal_law_traffic",
            "title": "Criminal Law - Traffic Accident Crime and Dangerous Driving Crime",
            "content": """Article 133 [Traffic Accident Crime] Whoever violates traffic and transportation management regulations, thereby causing a major accident resulting in serious injury or death, or causing major damage to public or private property, shall be sentenced to fixed-term imprisonment of not more than three years or criminal detention; whoever escapes after a traffic accident or has other particularly egregious circumstances shall be sentenced to fixed-term imprisonment of not less than three years but not more than seven years; whoever causes death due to escape shall be sentenced to fixed-term imprisonment of not less than seven years.

Article 133-1 [Dangerous Driving Crime] Whoever drives a motor vehicle on the road under any of the following circumstances shall be sentenced to criminal detention and shall also be fined:
(1) Chasing and racing, if the circumstances are egregious;
(2) Driving a motor vehicle while intoxicated;
(3) Engaging in school bus services or passenger transportation, seriously exceeding the rated number of passengers, or seriously exceeding the prescribed speed limit;
(4) Transporting hazardous chemicals in violation of safety management regulations on hazardous chemicals, endangering public safety.

Standard for drunk driving: blood alcohol content reaching 80 mg/100 ml or more."""
        },
        {
            "doc_id": "criminal_law_corruption",
            "title": "Criminal Law - Embezzlement",
            "content": """Article 382 [Embezzlement] Any state functionary who, by taking advantage of their position, embezzles, steals, swindles, or unlawfully appropriates public property by other means constitutes the crime of embezzlement.

Article 383 [Penalties for Embezzlement] Whoever commits the crime of embezzlement shall be punished according to the severity of the circumstances, in accordance with the following provisions:

(1) If the amount is relatively large or there are other relatively serious circumstances, the sentence shall be fixed-term imprisonment of not more than three years or criminal detention, and a fine shall also be imposed.
(2) If the amount is huge or there are other serious circumstances, the sentence shall be fixed-term imprisonment of not less than three years but not more than ten years, and a fine or confiscation of property shall also be imposed.
(3) If the amount is especially huge or there are other especially serious circumstances, the sentence shall be fixed-term imprisonment of not less than ten years or life imprisonment, and a fine or confiscation of property shall also be imposed; if the amount is especially huge and causes particularly heavy losses to the state and the people, the sentence shall be life imprisonment or death, and confiscation of property shall also be imposed.

Amount standards for embezzlement:
1. Relatively large amount: 30,000 yuan or more but less than 200,000 yuan
2. Huge amount: 200,000 yuan or more but less than 3 million yuan
3. Especially huge amount: 3 million yuan or more"""
        }
    ]
    
    return documents


if __name__ == "__main__":
    # Build evaluation dataset
    builder = LegalDatasetBuilder()
    dataset = builder.build_dataset("legal_qa_dataset.json")
    
    print(f"Dataset created with {len(dataset['simple_cases'])} simple cases and {len(dataset['complex_cases'])} complex cases")
    
    # Create legal documents
    documents = create_legal_documents()
    
    # Save documents
    with open("legal_documents.json", 'w', encoding='utf-8') as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)
    
    print(f"Created {len(documents)} legal documents for knowledge base")
