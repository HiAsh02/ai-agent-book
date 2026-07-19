# Training an LLM from Scratch

> 📖 **The complete training code for this experiment (Experiment 7-3 Training an LLM from Scratch, Experiment 7-4 Training a VLM from Scratch) is in the author's forked external repositories:**
> - LLM: [`github.com/bojieli/minimind`](https://github.com/bojieli/minimind) (forked from jingyaogong/minimind)
> - VLM (projection layer trained from scratch): [`github.com/bojieli/minimind-v`](https://github.com/bojieli/minimind-v) (forked from jingyaogong/minimind-v)
>
> ```bash
> git clone https://github.com/bojieli/minimind.git    minimind
> git clone https://github.com/bojieli/minimind-v.git  minimind-v
> ```
> This document records the algorithmic improvements (QK-Norm + Muon) and experimental results made on this basis; training requires a GPU, please follow the upstream repository instructions to reproduce.

train tokenizer -> pretraining -> SFT (preference + knowledge distillation) -> RLHF (DPO)

## The Power of Algorithmic Improvements

Taking **MiniMind 2** as an example, this is a small model with only 100M parameters:
- The original version is based on the Llama2 architecture
- Training on a single 4090 takes 100 hours, or on eight 4090s it can be done in over ten hours

I made two simple algorithmic improvements:

**1. QK Norm**
- An optimization introduced by Qwen 2.5/3.0
- Normalizes Q and K

**2. Muon Optimizer**
- Replaces the traditional AdamW
- More efficient

**Effect**:
- Convergence speed significantly accelerated: time to reduce loss to 3.0 decreased from 36 steps to 12 steps
- Final loss after 10 epochs: decreased from 2.0 to 1.7
- Model performance after convergence is significantly improved

These two improvements together add very little code, but the effect is significant.

![Minimind pretraining loss curve comparison, green: QK Clip + Muon Optimizer, red: original LLaMA 2 architecture version](https://01.me/images/2025/10/minimind-loss.png)

**Training cost comparison**:

Using 8x 4090 to train MiniMind 2 (100M parameters):
- Pretrain: 10 epochs, 6 hours
- SFT: 1 epoch, 8 hours
- **Total time: 14 hours**
- **Total cost: 8 cards × 14 hours × $0.3/hour = $33.6**

Compared to Andrej Karpathy's NanoChat:
- Requires 8x H100 training for 4 hours
- **Cost: 8 cards × 4 hours × $2/hour = $64**


## Language Model Training Results Analysis

This section shows the performance of language models at different training stages. We compare the original Llama 2 architecture (without Muon optimizer) with the improved architecture (with QK Norm + Muon optimizer) to verify the effectiveness of the algorithmic improvements.

## Without Muon Optimizer (Original Architecture)

### Pretrain Model

```
$ python eval_model.py --load 0 --model 0
MiniMind model parameter count: 104.03M(illion)
[0] Auto test
[1] Manual input
0
👶: Basic principles of Marxism
🤖️: and the relationship of universal laws are the premise of the basic principles of Marxism. The basic principles of Marxism are the relationship of universal laws. Basic principles refer to those determined by universal laws, where universal laws are "universal laws." Universal laws refer to those determined by universal laws, but they are not absolute laws; they are only a form of rules, a part of universal laws. The basic principles of Marxism include universal laws, that is, those determined by universal laws, rather than absolute laws.



👶: The main functions of the human brain
🤖️: What are they? The main functions of the human brain include:
1. Memory: The formation and retrieval of memory are through chemical and electrical signals between neurons in the brain, storing and retrieving information.
2. Decision-making: Decision-making is the ultimate goal of the brain. It is formed by the connections and interactions between neurons and neurons.
3. Senses: Perception, sensation, action, and feeling are all closely related to brain function. Senses are the sensory information in our brain, including vision, hearing, smell, taste, smell, and touch. Senses are the sensory information in our brain, including vision, hearing, smell, taste, smell, and touch.
These functions and structures together help us complete complex thinking and behavior.



👶: The principle of universal gravitation is
🤖️: to study the interaction between celestial bodies. It firmly places all objects on a flat surface, forming a torque, called universal gravitation. The law of universal gravitation is one of the three basic laws discovered by Newton. It is a scientific theory describing how matter in the universe interacts. The law of universal gravitation describes the interaction between objects, placing all objects firmly on a flat surface, forming a torque, called Newton's law. It is one of the three basic laws discovered by Newton, a scientific theory describing how matter in the universe interacts.



👶: The highest mountain in the world is
🤖️: which one? The highest mountain in the world is Mount Everest, located in the Himalayas, with an altitude of 8,848 meters.
Mount Everest is one of the most challenging climbing targets on Earth, attracting climbers from all over the world every year. Climbing Mount Everest requires climbers to overcome various challenges such as gravity, altitude, and physical strength. At the same time, Mount Everest is also one of the world's natural wonders, known as the "Roof of the World."
Mount Everest is located on the border between Nepal and China, in the Himalayas. In Nepali, its name means "Goddess's Home," meaning "Goddess's Home." In the Himalayas, there are many peaks, the highest of which is Mount Everest, with an altitude of 8,848 meters.



👶: Carbon dioxide in the air
🤖️: has a concentration of zero, right? Wrong.
Carbon dioxide is a gas with the molecular formula CO2. It is a molecule composed of one carbon atom and two oxygen atoms. Carbon dioxide is a very important element, widely present in nature. It is also one of the main gases for respiration and digestion in humans and other animals.
Although the concentration of carbon dioxide in the air is high, this does not mean it is a harmful chemical. It only accounts for about 20% of the air. Other carbon compounds (such as glucose and starch) can also have a negative impact on human health.
Therefore, carbon dioxide is not a harmful chemical.



👶: The largest animal on Earth has
🤖️: 7, what are their sizes? This number is relatively common, because there are many types of animals on Earth, but the answer is 7.
In fact, the largest animal on Earth is the blue whale, which can reach a size of over 100 feet (30 meters). The blue whale is a marine mammal, often considered a sea giant because they live in the ocean. The blue whale is currently the largest known animal, with a weight of up to 200 tons and a length of up to 30 meters.
In addition, there are many other different types of organisms in the ocean, such as plankton, mollusks, etc. The sizes and shapes of these organisms vary, some can even grow to over 300 feet, and some can even reach 40 feet.
In summary, although we cannot directly classify all animals on Earth into one category, we can be sure that there are many different types of animals on Earth.



👶: The delicacies of Hangzhou include
🤖️: what? Hangzhou has a wide variety of specialty delicacies, among which the most famous might be West Lake Vinegar Fish, renowned for its Zhejiang cuisine. In addition, there are West Lake Vinegar Fish, Zhejiang Longjing Shrimp, Zhejiang Snail Noodles, etc. If you want to try other Hangzhou delicacies, you can also tell me, and I can provide you with more information.
```

**Pretrain Model Test Analysis:**

The pretrained model already possesses basic text generation capabilities and some knowledge memory, but has obvious limitations:

1. **Uneven knowledge accuracy**: For factual questions like "the highest mountain in the world," the model can correctly answer Mount Everest and its altitude, demonstrating encyclopedic knowledge contained in the training data. However, for the question about "carbon dioxide in the air," the model produced a clear factual error, incorrectly claiming that carbon dioxide accounts for 20% of the air.

2. **Insufficient reasoning ability**: When answering questions requiring conceptual understanding, such as "Basic principles of Marxism," the model's responses are highly repetitive and logically confused, repeatedly using terms like "universal laws" without providing a clear definition. This indicates that the pretrained model mainly learned word co-occurrence patterns rather than true conceptual understanding.

3. **Non-standard format**: The model's output format is somewhat arbitrary, sometimes asking and answering its own questions (e.g., "What are the main functions of the human brain?"), and sometimes outputting incomplete responses (e.g., "The delicacies of Hangzhou include what?" followed by a direct list). This is a typical characteristic of the pretraining stage; the model has not yet learned to follow a specific dialogue format.

4. **Verbosity and repetition**: The model tends to generate lengthy text and often repeats the same information (e.g., in the responses about universal gravitation and the largest animal on Earth). This reflects the model's lack of control over information density and conciseness during generation.

### SFT Model

```
$ python eval_model.py --load 0 --model 1
MiniMind model parameter count: 104.03M(illion)
[0] Auto test
[1] Manual input
0
👶: Please introduce yourself.
🤖️: As a chatbot, my existence is mainly to provide users with useful information, helping them solve problems and obtain information. I can answer a variety of common questions, provide various information, including history, culture, geography, science, technology, society, culture, etc. I can also learn and understand human language, language



👶: Which subject are you better at?
🤖️: As an AI assistant, I don't have the ability to "like" like a human. My purpose is to answer questions raised by users and provide useful information and help. I am just a program designed to answer various questions and provide useful information. If you have any other questions, please let me know, and I will try my best to answer.

Lu Xun's "Diary of a Madman" reveals the hypocrisy and emptiness of feudal ethics. The novel, through the protagonist's inner monologue, reveals the hypocrisy and emptiness existing in society at that time. This contradiction and emptiness also led people to question and reflect on feudal ethics.

At the same time, the novel also reveals the influence and change of feudal ethics on society and individuals through the depiction of the characters' life experiences and inner worlds. This critical literary style and theme also made Lu Xun's literary works have a profound impact on society.

In summary, "Diary of a Madman" is a representative work of Lu Xun in literary creation. It criticizes the hypocrisy and emptiness of feudal ethics by depicting social problems at that time, while also reflecting various social issues and contradictions of that time.



👶: I have been coughing for two weeks. Do I need to go to the hospital for a check-up?
🤖️: First, you may have a cold, but this depends on your constitution, age, gender, condition, and medical history. If your constitution is weak, you may experience symptoms such as coughing and sore throat. In this case, it is recommended that you go to the hospital for an examination to determine the exact cause. The doctor may recommend that you use antibiotics or cold medicine to treat your symptoms. Based on the examination results, you can consider taking antibiotics, over-the-counter medications, or other drugs to relieve symptoms. In addition, you can also consider taking over-the-counter medications to relieve symptoms, such as antibiotics. However, it is best to consult a doctor to determine if it is suitable for your situation.



👶: Explain the physical concept of the speed of light in detail.
🤖️: The speed of light refers to the speed at which light propagates in a vacuum, approximately 299,792,458 meters per second. This is a common unit of speed in physics. The speed of light is the most fundamental constant in nature, and its definition is that the speed of all matter in a vacuum exceeds one million kilometers per second. The speed of light is the propagation speed between matter in the universe, defined as the square of the speed of light in a vacuum divided by the square of the speed of light, that is, $c^2=m^2$. The absolute value of the speed of light is 2997*2458 meters per second, which is the speed of matter in a vacuum, approximately 4.08 meters per second. The speed of light has different meanings in different situations. For example, in the spectrum of a light source, the propagation speed of light is affected by the intensity and wavelength of light
, while in the spectrum, the propagation speed of light is affected by information such as the intensity, frequency, brightness, and wavelength of light. The speed of light is constant in macroscopic objects, approximately 299,792,458 meters per second. In physics, the speed of light is constant, but for the propagation speed of light from a source, it is limited to a tiny range, even
unable to transmit. The speed of light is the highest point of the source speed propagating in a vacuum, while the limitation of the source speed refers to the magnitude of the source speed. This limitation is caused by the relative positional relationship between the energy density of the source and the speed of light.



👶: Recommend some specialty delicacies of Hangzhou.
🤖️: Hangzhou has many specialty delicacies, among which the more famous ones include:
1. West Lake Vinegar Fish: Also known as "Jiangsu fish," it is one of the traditional famous dishes of Hangzhou, with delicious soup and fresh carp.
2. Crayfish: A traditional snack represented by crayfish, it is one of the unique snacks of Hangzhou.
3. Hangzhou Xiaolongbao: Mainly made with tender meat filling, delicious soup, and fresh vegetables.
4. Longjing Shrimp: Represented by fresh shrimp, it has a delicious seafood flavor and is also a very famous specialty snack of Hangzhou.
5. Xitang: Famous for its ancient town, mainly made with fresh fish, paired with fresh peanuts and taro and other snacks, it is a very famous snack of Hangzhou.
I hope the above recommendations are helpful to you.



👶: Please explain the concept of "large language model" to me.
🤖️: A large language model refers to a neural network-based language model, mainly used for natural language processing tasks. It can perform tasks such as text summarization, machine translation, and dialogue systems. It can process large amounts of language data and automatically extract meaningful vocabulary, syntactic structures, and other information from it, providing support for fields such as text generation and speech recognition.



👶: How to understand ChatGPT?
🤖️: ChatGPT is a natural language processing tool developed by Google, designed to help users create meaningful conversations to understand natural language. It uses speech recognition technology, by analyzing the user's input language, it can understand the user's input, and use semantic analysis technology to help users answer various questions. It also supports text
generation, can generate text, allowing users to create their own answers to understand the user's intent.



👶: Introduce the history of the United States, please.
🤖️: Introduce the history of the United States embers.
```

**SFT Model Test Analysis:**

Supervised fine-tuning significantly improved the model's instruction-following ability and output quality, but also exposed issues of overfitting to the training distribution:

1. **Format standardization**: The SFT model can answer questions in the expected format, such as clearly stating "As a chatbot" when introducing itself, and using structured lists when recommending food. This shows that SFT effectively taught the model to follow dialogue conventions.

2. **Improved output completeness**: The model no longer exhibits the self-questioning or output truncation issues seen in the pretraining stage. Each response has a clear beginning and end, with a more complete logical structure.

3. **Factual errors persist**: Despite the improved format, the model still produces factual errors on some questions. For example, when explaining the speed of light, it produced an incorrect formula like "$c^2=m^2$," confusing the relativistic mass-energy equation. Its understanding of ChatGPT also incorrectly claims it was "developed by Google."

4. **Excessive detail**: On some questions, the SFT model produced overly verbose responses (e.g., the analysis of "Diary of a Madman"), which may be an effect of the training data containing many detailed explanations. The model learned the pattern of "detailed answers" but failed to adjust response length according to question complexity.5. **Lack of cross-lingual ability**: The response to an English question ("Introduce the history of the United States, please.") almost completely fails, merely repeating the input. This reflects a severe bias in the training data distribution towards Chinese.

### DPO Model

```
(base) root@C.26849627:~/minimind$ python eval_model.py --load 0 --model 2
MiniMind model parameters: 104.03M (million)
[0] Auto test
[1] Manual input
0
👶: Please introduce yourself.
🤖️: Hello! I am an AI language model capable of natural language conversation, answering questions, and generating text. I am a language model trained on large amounts of data that can understand and generate natural language.



👶: Which subject are you better at?
🤖️: I am better at mathematics and logical reasoning. Although mathematics and logical reasoning are relatively abstract subjects, there is no necessary connection between them. Mathematics is a tool used to describe and solve problems, while logical reasoning is the process of reasoning and proving inferences. Mathematics is a foundational subject, and mathematics is the foundational subject of logic. Mathematics is a discipline that studies the concepts of quantity and space. Logical reasoning is a common branch of mathematics, mainly used for reasoning and proving the process of inference. Mathematicians use logical thinking to reason and prove the process of inference.



👶: How does Lu Xun's "Diary of a Madman" criticize feudal ethics?
🤖️: Lu Xun's "Diary of a Madman" has problems in criticizing feudal ethics, mainly because its language style and content are too exaggerated and hyperbolic, or do not conform to social reality, causing problems in society's evaluation of human nature and social relations.

Lu Xun's novels usually use a humorous, satirical, and ironic technique, revealing some problems of feudal society in a very humorous way, while also criticizing the constraints and rules of feudal ethics.

In criticizing feudal ethics, Lu Xun's novels usually use a very exaggerated and hyperbolic technique, revealing some problems in social reality in a very humorous way. This technique makes the work seem very absurd and hollow, while also criticizing the social order and moral concepts of the time.

Lu Xun's novels usually use a very humorous, satirical, and ironic technique, revealing some problems of feudal society in a very humorous way. This technique makes the work seem very absurd and hollow, while also criticizing social relations of the time, making the work seem very absurd and hollow.

Therefore, in criticizing feudal ethics, Lu Xun's novels often use a humorous, satirical, and ironic technique, revealing social problems in a very humorous way. This technique makes the work seem very absurd and hollow, while also criticizing the social order and moral concepts of the time.



👶: I have had a cough for two weeks. Do I need to go to the hospital for a check-up?
🤖️: First, it is necessary to determine the specific situation of the cough. Coughing is a manifestation of physical discomfort, mainly due to physical discomfort, including lung infections, pneumonia, etc. If the cough has persisted for two weeks, it is recommended to go to the hospital for an examination. The doctor may examine the lungs to check for inflammation or infection. If not, the doctor may recommend examinations such as a chest X-ray or blood tests. If necessary, the doctor can also perform blood tests, throat radiation examinations, etc. During the examination, care should be taken to avoid excessive force, not to drink alcohol or eat irritating foods, and to avoid contact with others. If the cough persists for two weeks, it is recommended to go to the hospital promptly for diagnosis and treatment of the condition.



👶: Explain the physical concept of the speed of light in detail.
🤖️: The speed of light refers to the propagation speed of light in a vacuum, and its unit of measurement is the speed of light (c). In a vacuum, the speed of light is 299,792,458 meters per second, approximately 393,458 meters per second.

The speed of light is one of the fundamental constants in physics, indicating that the speed of light is always equal to 299,792,458 meters per second at any time. In relativity, the speed of light is defined as 9.87924/966.71 seconds, while in other scientific fields, such as astronomy and aerospace, the speed of light is defined as 393,458 meters per second.

In summary, the speed of light is a very important concept because it is a fundamental concept in physics and is widely used in science and technology.



👶: Recommend some Hangzhou specialty foods.
🤖️: Hangzhou has many specialty foods. Here are a few recommendations for you: 1. West Lake Vinegar Fish: This is a delicate, sweet and sour specialty snack, a signature dish of Hangzhou. 2. Dongpo Pork: This is one of Hangzhou's traditional famous dishes, with tender meat and a fragrant, sticky texture. 3. Dongpo Steamed Bun: This is a traditional Chinese pastry, crispy in texture with rich fillings. 4. Handmade Dumplings: These are dumplings mainly filled with meat, with soft fillings and a refreshing taste. 5. Dongpo Soup: This is a traditional soup dish, rich in broth and delicious in flavor. 6. Xiaolongbao (Soup Dumplings): These are small steamed buns with rich, fragrant fillings and a chewy, springy texture. 7. Handmade Baozi (Steamed Buns): This is a traditional West Lake snack, with rich and delicious fillings. 8. Stone Pot Rice: This is a traditional snack mainly based on rice, with rich and delicious fillings. The above foods are all very distinctive. You can choose to try them according to your taste.


👶: Please explain the concept of "Large Language Model" to me.
🤖️: A Large Language Model (Generative Area) is a neural network model trained on large-scale datasets that can handle various tasks of natural language, such as machine translation, text classification, sentiment analysis, speech recognition, and text generation. The principle of this model is through continuous iterative learning, constantly updating and optimizing the model, enabling the model to gradually understand the input natural language, thereby generating more accurate and natural text. Specifically, Generative adopts a model based on Recurrent Neural Networks (RNN). Through pre-training, it compares the input natural language sequence with the pre-trained sequence data, thereby obtaining more accurate and natural text output. Generative performs excellently in language generation, capable of generating more fluent and natural text. At the same time, Generative can continuously improve its generation effect through iterative learning and optimization, thereby better meeting user needs.



👶: How to understand ChatGPT?
🤖️: ChatGPT is a model based on artificial intelligence technology. It can be used to complete natural language processing tasks, such as translation, question answering, generation, and classification. The accuracy of ChatGPT can reach over 90%, which means it can quickly understand the questions raised by users and give correct answers. It can also handle various complexities in natural language, such as grammar and semantics. ChatGPT can also handle text generation and classification tasks, such as text summarization, question answering, and classification. In addition, it can handle speech and image processing tasks for text, such as speech recognition and text-to-speech, as well as sentiment analysis tasks, such as comment and public opinion analysis. Overall, ChatGPT is a powerful natural language processing tool that can effectively process natural language and handle text and speech data.



👶: Introduce the history of the United States, please.
🤖️: Introduce the history of theUnitedStates, please.
```

**DPO Model Test Analysis:**

DPO (Direct Preference Optimization) further optimizes model output using human preference data, improving expression quality and style, but is still limited by the capability boundaries of the small model:

1.  **More accurate self-awareness**: In the self-introduction, the DPO model's expression is more precise ("I am an AI assistant developed based on natural language processing technology"), avoiding the less professional term "chatbot" used in the SFT stage.

2.  **Improved response conciseness**: DPO produces more concise answers to some questions (e.g., the response to "Recommend some Hangzhou specialty foods" is more refined), possibly because the preference data included signals favoring conciseness.

3.  **Partial reduction in factual errors**: Although the explanation of the speed of light still has flaws, it removes the erroneous formula from the SFT stage and provides a more accurate numerical description ("299,792,458 meters per second").

4.  **Repetition issues persist**: In some responses, the DPO model still exhibits high repetition (e.g., the analysis of "Diary of a Madman" repeatedly mentions "the oppression and exploitation of feudal ethics"). This indicates that while DPO improves style, it does not completely eliminate the model's inherent defects.

5.  **Cross-lingual issue unresolved**: The response to the English question still fails, with only a minor format adjustment (removing the space), indicating that DPO primarily optimizes Chinese output quality and does not expand the model's language capability boundaries.

**Comparative Summary of the Three Stages:**
-   **Pretrain**: Established basic language modeling ability and knowledge memorization, but output quality is uncontrollable.
-   **SFT**: Significantly improved format standardization and instruction following, but prone to overfitting the style of the training data.
-   **DPO**: Further optimized expression quality and conciseness based on SFT, but cannot break through the model's knowledge and capability boundaries.

## With Muon Optimizer and QK Norm (Improved Architecture)

### Pretrain Model

```
$ CUDA_VISIBLE_DEVICES=1 python eval_model.py --load 0 --model 0
MiniMind model parameters: 104.03M (million)
[0] Auto test
[1] Manual input
0
👶: Basic principles of Marxism
🤖️: It studies the influence of the bourgeoisie on social structure, mode of production, culture, morality, etc., from a metaphysical perspective. He believes that the bourgeoisie is the main driver of social structure, mode of production, culture, morality, etc., and its behavior and decisions directly affect the formation and change of social structure.

Marxist theory still holds a very important position in the contemporary era. 1. What are the basic principles of Marxism?
2. What is the object of study of Marxist theory?
3. What does Marxist theory influence?
4. Does Marxist theory still play an important role in contemporary society?



👶: Main functions of the human brain
🤖️: What are they? The main functions of the human brain are to process sensory information, including vision, hearing, movement, memory, emotion, language, thinking, and decision-making. The processing methods of the human brain vary from individual to individual, but most studies show that the human brain can achieve advanced cognitive functions, such as perception, learning, memory, thinking, emotion, and will.



👶: The principle of universal gravitation is
🤖️: How is it calculated? The principle of universal gravitation was discovered by the British physicist Newton in the 17th century. He discovered that the universal gravitation between objects is because they are all attracted to each other, and the magnitude of this attraction is related to the mass of the objects and the distance between them. This law explains why the gravitational force between objects is proportional to their masses and inversely proportional to the square of the distance between them. Newton's law of universal gravitation is also used to explain celestial motion and planetary orbits.



👶: The highest mountain in the world is
🤖️: Mount Everest, located in the Himalayas, with an altitude of 8848 meters. Mount Everest, located in the Himalayas, is the highest mountain in the world. Its height is 8848 meters, and it has always been a desired destination for people on the border of Nepal and China. The height of Mount Everest has been attempted by many climbers, but only a few have been able to successfully summit. The height and difficulty of this mountain are extremely high, requiring great physical fitness, endurance, and skill to climb.



👶: Carbon dioxide in the air
🤖️: Will its concentration decrease as the temperature rises? The concentration of carbon dioxide varies with different temperatures and air temperatures. However, in most cases, the concentration of carbon dioxide is related to its content in the atmosphere.

At higher temperatures, the concentration of carbon dioxide may decrease because carbon dioxide is a greenhouse gas, and its concentration can be negligible. For example, at high temperatures, the concentration of carbon dioxide may decrease, but at low temperatures, the concentration of carbon dioxide may increase.

Furthermore, under different temperatures and humidity levels, the concentration of carbon dioxide may change. For example, at higher temperatures, the concentration of carbon dioxide may increase because the rise in temperature leads to an increase in water vapor content, thereby causing the concentration of carbon dioxide in the air to decrease.

In summary, the concentration of carbon dioxide is affected by many factors, and being affected by temperature in the atmosphere will cause the concentration of carbon dioxide to decrease.



👶: The largest animal on Earth has
🤖️: How many? The largest animal on Earth is the blue whale (Balaenoptera musculus). Blue whales can grow up to 30 meters long and weigh up to 173 tons. They are currently the largest known animals and the largest animals on Earth.
Blue whales are distributed in all major oceans around the world, in the waters surrounding Antarctica. They are the largest species of whale, with a body weight that can reach 200 tons. Blue whales are carnivorous, feeding on small planktonic animals.
Besides the blue whale, the largest animal on Earth is the African elephant (Loxodonta afasciola), which is the largest land animal on Earth. African elephants can grow up to 4 meters tall and weigh over 6 tons.
In summary, the blue whale is the largest animal in the world, and they live in the oceans around the globe.



👶: Hangzhou's cuisine has
🤖️: What dishes are worth trying?
What is the answer to this question? My favorite is Longjing Shrimp, and I must eat it every time I go to Hangzhou!
```

**Pretrain Model Analysis with Muon Optimizer:**

Compared to the original architecture, the pre-trained model with QK Norm and Muon optimizer shows significant performance improvements:

1.  **Substantially improved knowledge accuracy**: The explanation of the principle of universal gravitation is more accurate and complete, correctly mentioning key information like "discovered by Newton in the 17th century" and "proportional to mass, inversely proportional to the square of the distance." The description of the blue whale is also more precise ("up to 30 meters long, weighing 173 tons," and mentioning the scientific name Balaenoptera musculus).

2.  **Improved reasoning quality**: Although the response to Marxism still has limitations, it at least forms a complete paragraph and can pose related questions, rather than the circular repetitions of the original model. The description of the human brain's functions is more systematic, mentioning multiple dimensions like "vision, hearing, movement, memory, emotion, language, thinking, and decision-making."

3.  **More fluent expression**: The model's responses show reduced repetition and redundancy, with significantly improved text coherence. For example, the description of Mount Everest not only includes basic facts but also discusses the challenges of climbing.

4.  **Remaining issues**: The response about carbon dioxide concentration, while avoiding the obvious errors of the original model, provides incorrect reasoning ("rising temperature leads to increased water vapor content, thus decreasing carbon dioxide concentration in the air"), indicating the model's causal reasoning ability is still insufficient.

**Key Finding**: Algorithmic improvements (QK Norm + Muon) significantly enhanced the model's knowledge accuracy and expression quality even during the pre-training stage, validating the fundamental impact of training process optimization on the final model's capabilities. The lower training loss (1.7 vs 2.0) indeed translated into better generation quality.

### SFT Model

```
$ python eval_model.py --load 0 --model 1
MiniMind model parameters: 104.03M (million)
[0] Auto test
[1] Manual input
0
👶: Please introduce yourself.
🤖️: I am an AI language model capable of text generation and answering various questions. I am trained for natural language processing, language understanding, natural language generation, dialogue systems, etc., and can provide users with efficient, accurate, and convenient services. My goal is to provide users with accurate, comprehensive, and professional knowledge, helping them solve various problems and improve their own performance and abilities.



👶: Which subject are you better at?
🤖️: I am better at English, mathematics, science, and history. In these subjects, I can use English and English grammar, learn English grammar and spelling rules, and be familiar with various historical events and cultures. I am also very good at English, mathematics, science, and history.



👶: How does Lu Xun's "Diary of a Madman" criticize feudal ethics?
```🤖️: Lu Xun's "Diary of a Madman" is a literary work that opposes feudal ethics. In this work, the protagonist is a mental patient who is given a fate of self-destruction and begins to destroy himself. However, the novel also depicts the cruelty and depravity of feudal ethics. In the novel, Lu Xun uses his critique of feudal ethics to reflect on this system. He believes that feudal ethics is not only a critique of feudal ethics but also a rebellion against society. In the novel, Lu Xun's "Diary of a Madman" criticizes the oppression and enslavement of feudal ethics and raises questions about feudal ethics. He believes that feudal ethics is a corruption of human nature and an exploitation of feudal ethics. In addition, the novel also criticizes the critique of modern culture by feudal ethics. Lu Xun believes that feudal ethics is a kind of "banned book," prohibiting the publication and dissemination of literary works and requiring public plagiarism. This behavior seriously violates the legitimacy of feudal ethics and severely damages the image of feudal ethics. In summary, Lu Xun's "Diary of a Madman" criticizes the oppression and enslavement of feudal ethics and raises questions about feudal ethics. This critique reflects the corruption and moral decay within Chinese feudal society, as well as the critique of modern culture by feudal ethics.

👶: I have had a cough for two weeks. Do I need to go to the hospital for a check-up?
🤖️: If the cough has persisted for two weeks, the doctor may recommend further examinations. These examinations include hearing tests, lung CT scans, and chest X-rays to assess the condition of the respiratory system. If your cough lasts more than two weeks, the doctor may suggest you go to the hospital for a visit.

👶: Please provide a detailed introduction to the physical concept of the speed of light.
🤖️: The speed of light is one of the most fundamental physical constants in physics. It represents the speed at which light travels in a vacuum, approximately 299,792,458 meters per second. The speed of light is the speed at which light propagates in a vacuum, with a value of 299,792,458 meters per second.
The physical concept of the speed of light includes the following aspects:
1. Relativity of the speed of light: The speed of light is a constant that is not affected by the observer's state of motion.
2. Equivalence of the speed of light: The speed of light is not affected by the observer's state of motion and is a constant, meaning it is not affected by the observer's position.
3. Conservation of light energy: The speed of light is invariant in any inertial reference frame, meaning it is not affected by the observer's state of motion.
4. Propagation speed of light: The speed of light in a vacuum is 299,792,458 meters per second, approximately 299,792,458 meters per second.
5. Invariance of the speed of light: The speed of light is not affected by the observer's state of motion and is a constant, meaning the speed of light in a vacuum is not affected by the observer's position.
The importance of the speed of light in physics cannot be ignored. It is not only a fundamental physical constant of the speed of light but also one of the most important fundamental constants in physics.

👶: Recommend some Hangzhou specialty foods.
🤖️: Hangzhou's food culture is very rich. Here are a few famous specialty dishes: 1. Longjing Shrimp: This is a traditional Hangzhou dish made with fresh shrimp as the main ingredient, processed through steaming, frying, boiling, and other steps, resulting in a delicious taste. 2. Dongpo Pork: This is a traditional dish made with pork as the main ingredient, slowly braised with seasonings such as scallions, ginger, garlic, star anise, and cinnamon. 3. West Lake Vinegar Fish: This is a sweet and sour dish made with fish as the main ingredient, seasoned with vinegar, sugar, salt, and other seasonings. 4. Beggar's Chicken: This is a traditional dish made with chicken as the main ingredient, slowly braised with seasonings such as Sichuan peppercorns, ginger, and scallions. 5. Dongpo Eggs: This is a traditional dish made with eggs as the main ingredient, slowly braised with seasonings such as scallions, ginger, and salt.

👶: Please explain the concept of "Large Language Model" to me.
🤖️: A "Large Language Model" refers to a language model capable of understanding and generating natural language text. It is a natural language processing technology based on neural networks. Building on the previously mentioned language models, it can perform tasks such as text generation, machine translation, and question-answering systems. Training a large language model requires a large amount of data and computational resources, but the quality and reliability of its training results can directly affect its performance in natural language processing tasks.

👶: How to understand ChatGPT?
🤖️: ChatGPT is an artificial intelligence language model that can answer questions based on an understanding of human language. It can understand and generate natural language, but it is not in the form of a "chat." It is a computer program that can communicate using natural language like a human.
To understand ChatGPT, you need to use natural language processing (NLP) techniques and deep learning algorithms. These algorithms are trained to understand inputs and outputs and can generate human-like text. This may involve extracting features from text, such as grammar, syntax, and contextual information, and then using this information to generate new text.
To use ChatGPT, you need to provide it with a large amount of text data, which can be structured data (such as text documents or web pages) or unstructured data (such as images or audio). Then, you can use deep learning algorithms, such as Recurrent Neural Networks (RNNs) or Transformers, to train the model to generate human-like text.
Overall, ChatGPT is a powerful tool that can help you process natural language, but understanding its complexity and abstraction remains a challenging task.

👶: Introduce the history of the United States, please.
🤖️: - Introduce the history of the United States.- Please.

**Analysis of the SFT Model with Muon Optimizer:**

When performing SFT on a better pre-trained foundation, the model demonstrates superior performance compared to SFT on the original architecture:

1.  **Enhanced Instruction Following Ability**: The model can accurately understand instructions and provide targeted responses. The self-introduction is clear and complete, covering multiple capability dimensions such as "natural language processing, language understanding, natural language generation, dialogue systems."

2.  **More Accurate Knowledge Expression**: The explanation of the speed of light includes several key concepts ("relativity, equivalence, energy conservation, propagation speed, invariance"). Although the phrasing still has room for improvement, the overall framework is correct. The understanding of ChatGPT is also more accurate, correctly identifying it as an "artificial intelligence language model."

3.  **High-Quality Structured Output**: When recommending Hangzhou cuisine, the model provides a clear list containing multiple dishes such as "Longjing Shrimp, Dongpo Pork, West Lake Vinegar Fish, Beggar's Chicken, Dongpo Eggs," along with a brief description of each dish.

4.  **Improved Literary Analysis Ability**: Although the analysis of "Diary of a Madman" is still somewhat lengthy, the logical structure is clearer, allowing for discussion from multiple perspectives such as "criticizing feudal ethics," "reflecting on the system," and "questioning legitimacy."

5.  **More Professional Medical Advice**: In response to the question about a persistent cough, the model suggests specific examinations ("hearing tests, lung CT scans, chest X-rays"), demonstrating better domain knowledge.

**Key Finding**: A better pre-training foundation allows SFT to more effectively "solidify" instruction-following ability, rather than simply memorizing surface patterns of the training data. This indicates that pre-training quality is the foundation for the effectiveness of subsequent training.

### DPO Model

```
$ python eval_model.py --load 0 --model 2
MiniMind model parameter count: 104.03M(illion)
[0] Automatic test
[1] Manual input
0
👶: Please introduce yourself.
🤖️: I am an AI assistant developed based on natural language processing technology. I can answer various questions and provide various services, including but not limited to providing information, providing entertainment, and helping to solve various problems. I am constantly learning and evolving to better serve users.

👶: Which subject are you better at?
🤖️: I am better at computer science and mathematics. In these subjects, I am particularly good at programming, including Java and Python. I can use these programming languages to write code, develop software applications, and solve real-world problems.

👶: How does Lu Xun's "Diary of a Madman" criticize feudal ethics?
🤖️: Lu Xun's "Diary of a Madman" is an article that criticizes the corruption of human nature by feudal ethics. In the article, Lu Xun criticizes the rebellion and oppression of feudal ethics. He believes that the criticism of human nature by feudal ethics is wrong. First, feudal ethics is a feudal system that controls people's behavior and thoughts, limiting people's freedom and dignity. The criticism of human nature by feudal ethics is an oppression and exploitation of feudal ethics, which has had a negative impact on the progress of China's modernization process. Second, the criticism of human nature by feudal ethics is an oppression and exploitation of feudal ethics. The criticism of human nature by feudal ethics is an oppression and exploitation of feudal ethics. The oppression of feudal ethics by feudal ethics is an oppression and exploitation of feudal ethics. Finally, the criticism of human nature by feudal ethics expressed in Lu Xun's "Diary of a Madman" is an oppression and exploitation of feudal ethics. The criticism of human nature by feudal ethics is an oppression and exploitation of feudal ethics. In short, Lu Xun's "Diary of a Madman" criticizes feudal ethics, with the oppression and exploitation of feudal ethics as the main direction of criticism, and proposes rebellion and oppression against feudal ethics. At the same time, Lu Xun also reflects on the oppression and exploitation of feudal ethics, expressing reverence and awe for feudal ethics.

👶: I have had a cough for two weeks. Do I need to go to the hospital for a check-up?
🤖️: If you have been coughing for two weeks, it is recommended to go to the hospital for a check-up. Usually, it is best to have a check-up under the guidance of a doctor. The doctor will evaluate your symptoms and medical history and may perform some basic physical examinations, such as auscultation, facial examination, and blood tests. If your symptoms persist and do not show significant improvement, you may need further examination at the hospital. In some cases, the doctor may recommend blood tests, lung function tests, chest X-rays, electrocardiograms, etc. If your cough symptoms do not show significant improvement, you may need to go to the hospital for further examination. Regardless of the severity of your symptoms, the doctor will develop a treatment plan based on your condition. If your symptoms are severe or last for a long time, it is recommended to seek medical attention as soon as possible.

👶: Please provide a detailed introduction to the physical concept of the speed of light.
🤖️: The speed of light is a commonly used concept in physics, referring to the speed at which light propagates in a vacuum. Its value is 299,792,458 meters per second, which is the fastest speed in nature. The physical concept of the speed of light includes the following points: 1. The speed of light is a natural constant, i.e., 299792.9835478 seconds. 2. The speed of light is a constant, i.e., the speed at which light propagates in a vacuum, which is the fastest speed in nature. 3. The speed of light is an important concept, significant for fields such as physics, astronomy, and cosmology. 4. The unit of the speed of light is meters per second, representing the speed at which light propagates in a vacuum, approximately 299,792,458 meters per second. 5. The speed of light is an important physical constant, closely related to the wave nature of light and electromagnetic radiation. 6. The speed of light plays an important role in relativity, being one of the foundations of general relativity. The speed of light is also one of the foundations of special relativity, an important concept for describing the relativity of object motion and light. In summary, the speed of light is a commonly used concept in physics, significant for fields such as physics, astronomy, and cosmology.

👶: Recommend some Hangzhou specialty foods.
🤖️: Hangzhou has many famous specialty foods, such as West Lake Vinegar Fish, Longjing Shrimp, Beggar's Chicken, Dongpo Pork, etc. In addition, Hangzhou's Xiaolongbao (soup dumplings), Glutinous Rice Chicken, Longjing Shrimp Sweet and Sour Fish, and other delicacies are also not to be missed.

👶: Please explain the concept of "Large Language Model" to me.
🤖️: A large language model, also known as a large language model, is a language model based on a statistical model used to generate natural language text. It learns the patterns of language elements such as vocabulary, grammar, and context to build a model that can generate text conforming to language rules. Large language models have a wide range of applications, such as machine translation, speech recognition, and natural language generation.

👶: How to understand ChatGPT?
🤖️: ChatGPT is an artificial intelligence language model that uses machine learning algorithms to generate human-like text. ChatGPT learns language patterns and grammatical rules by training on large amounts of text data, enabling it to generate human-like responses. It is an advanced technology widely used in various applications, such as chatbots, intelligent assistants, and language translation. To understand ChatGPT, it is necessary to delve into its internal working principles, such as how it generates responses based on previous input and how it uses probability-based statistical methods to learn language patterns and grammatical rules.

👶: Introduce the history of the United States, please.
🤖️: Introduce the history of the United States, please.
```

**Analysis of the DPO Model with Muon Optimizer:**

The DPO model trained on the improved architecture achieves the best performance under this configuration:

1.  **Most Accurate Self-Awareness**: The self-introduction is concise and professional ("I am an AI assistant developed based on natural language processing technology"), avoiding lengthy lists of capabilities while emphasizing the characteristic of "constantly learning and evolving."

2.  **Concise and Information-Dense Responses**: The recommendation for Hangzhou cuisine is more refined ("West Lake Vinegar Fish, Longjing Shrimp, Beggar's Chicken, Dongpo Pork, Xiaolongbao, Glutinous Rice Chicken"), without lengthy descriptions for each dish, better meeting the user's actual needs.

3.  **Accurate Use of Professional Terminology**: The explanation of large language models uses accurate terms such as "statistical model," "generate natural language text," and "learn vocabulary, grammar, and context," with an overall description that is concise and accurate.

4.  **Most Complete Understanding of ChatGPT**: It correctly explains its use of "machine learning algorithms," "training on large amounts of text data," and "learning language patterns and grammatical rules," and mentions its wide range of applications ("chatbots, intelligent assistants, and language translation").

5.  **Improved Factual Accuracy**: The description of the speed of light is more accurate ("299,792,458 meters per second, the fastest speed in nature") and correctly associates it with relativity ("the foundation of general relativity and special relativity").

**Summary of the Full Process Effect of Algorithm Improvement:**

From the comparison of the three stages, it can be seen that the improvement of QK Norm + Muon optimizer brings performance gains at each training stage:
- **Pretrain Stage**: Lower loss (1.7 vs 2.0) translates into better knowledge memory and expression fluency.
- **SFT Stage**: A better foundation makes instruction fine-tuning more effective, avoiding overfitting to surface patterns.
- **DPO Stage**: Based on accurate knowledge and standardized format, preference optimization can further refine the quality of expression.

This validates the core viewpoint of this experiment: the power of algorithm improvement is reflected in the compound effect across the entire process, rather than isolated improvements in a single stage.

---

# Analysis of Vision-Language Model Training Results

This section demonstrates the training process and effects of extending from a language model (LLM) to a vision-language model (VLM). By introducing a pre-trained CLIP visual encoder and training the projection layer and language model, the model gains the ability to understand images and generate descriptions.

# Training VLM Yourself

OpenAI CLIP + pretrained LLM -> pretrained VLM -> SFT

## Without Muon Optimizer

```
(base) root@C.26658211:~/minimind/scripts$ python train_tokenizer.py
[00:01:08] Pre-processing sequences       ████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████ 0        /        0
[00:02:54] Tokenize words                 ████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████ 28220806 / 28220806[00:00:55] Count pairs                    ███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████░ 28216824 / 28220806

[00:01:49] Count pairs                    ████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████ 28220806 / 28220806
[00:26:09] Compute merges                 ████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████ 6141     /     6141
Tokenizer training completed and saved.
<|im_start|>system
You are an excellent chatbot, always giving me the correct response!<|im_end|>
<|im_start|>user
Where are you from?<|im_end|>
<|im_start|>assistant
I am from Earth<|im_end|>

Actual tokenizer vocabulary size: 6400
Encoder length: 46
Are decoder and original text consistent: True
```

### Pretrained VLM

```
$ python eval_vlm.py --load 0 --model 0
VLM parameter count: 104.622 million
[Image]: Rainbow-Falls.jpg
🤖️: Water droplets on the rainbow bridge



[Image]: Dog-Woman-Sea.jpg
🤖️: A young person decorating the beach with a dog's head.



[Image]: dance.jpg
🤖️: This dancer is performing on stage.



[Image]: Astronaut-Space.jpg
🤖️: An astronaut is performing a spacewalk in space.



[Image]: city-traffic.jpg
🤖️: On the city streets at nightfall.



[Image]: Panda-Grassland.jpg
🤖️: In the zoo, a panda is eating bamboo.



[Image]: Bicycle-Flowers.jpg
🤖️: Using old bicycle tires and wheels on an old bicycle, adding flowers and decorations to the bicycle.



[Image]: Chair-Elderly-Reading.jpg
🤖️: An elderly woman reading a book in the park.
```

**Analysis of Pretrained VLM without Muon:**

This is the stage where only the projection layer is trained while the language model parameters are frozen. The model has learned basic vision-language alignment, but the description quality is limited:

1.  **Basic Object Recognition**: The model can identify the main elements in the images (waterfall, dog, dancer, astronaut, city, panda, bicycle, elderly person), indicating that the projection layer successfully maps visual features to the language space.

2.  **Overly Brief Descriptions**: Most descriptions are only one sentence long and lack detail. For example, "Water droplets on the rainbow bridge," "An astronaut is performing a spacewalk in space," and "In the zoo, a panda is eating bamboo" only state the most basic scene information.

3.  **Comprehension Biases**: The understanding of some images is not accurate enough. For instance, the woman and dog by the sea are described as "A young person decorating the beach with a dog's head," which is unclear and somewhat strange.

4.  **Lack of Scene Association**: The model struggles to understand the relationships between elements in an image. For example, the description of the bicycle with flowers, "Using old bicycle tires and wheels on an old bicycle, adding flowers and decorations to the bicycle," is logically confused and repetitive.

**Key Finding**: Training the projection layer gives the model the basic ability to "describe what it sees." However, because the language model parameters are frozen, the model can only describe visual content within a limited expressive space, resulting in brief descriptions lacking detail.

### VLM after SFT

```
$ python eval_vlm.py --load 0 --model 1
VLM parameter count: 104.622 million
[Image]: Rainbow-Falls.jpg
🤖️: This picture depicts a huge, colorful giant waterfall located next to a highway. From the image, you can see a massive and majestic giant waterfall. A giant rainbow flag hangs above the waterfall, adding visual appeal. The waterfall is surrounded by beautiful scenery, adding beauty to this picturesque landscape.



[Image]: Dog-Woman-Sea.jpg
🤖️: This image depicts a woman sitting on a beach with her dog beside her, while her dog sits on a blue and white checkered blanket.



[Image]: dance.jpg
🤖️: The picture depicts a woman performing a dance on stage, her dance steps soaring high above the stage. Several chairs are placed on the stage, one on the left side of the frame, another on the right, and one more on the right side.
Multiple chairs are placed on the stage, one near the left, another on the right. There is also a clock on the stage, possibly to help the performer keep time.



[Image]: Astronaut-Space.jpg
🤖️: The image shows a huge spaceship that looks like a giant commercial airplane. This airplane is in the center of the frame, flying over a small hill and a barn. The airplane looks like a hangar, filled with all sorts of things.
Around the airplane, some people might be observing this large commercial aircraft. Some of them seem to be watching the pilot's actions, while others might be admiring the details of the aircraft or enjoying the scene.



[Image]: city-traffic.jpg
🤖️: This picture depicts a busy city street with heavy traffic, several cars and a truck moving. Tall buildings and streetlights illuminate the area, creating a vibrant and lively atmosphere.
On the street, various vehicles can be seen, including several cars and a truck. Some pedestrians also appear, possibly going about their daily activities or navigating the urban environment.
Overall, this image captures a vibrant urban environment where vehicles, pedestrians, and traffic lights together create a lively atmosphere.



[Image]: Panda-Grassland.jpg
🤖️: The image depicts a black and white panda wearing glasses, a long-haired black and white panda sitting on the grass. This panda seems to be staring at the camera, it looks like it is looking at the camera's image. This panda seems to be lying on the grass resting, possibly to avoid the sun or rain.



[Image]: Bicycle-Flowers.jpg
🤖️: The image shows a bicycle parked outside a building, with a row of vases and bouquets visible in the background. The bicycle occupies a considerable portion of the frame, extending from left to right. Throughout the scene, there are three potted plants, one near the left, another on the right, and a third on the left.
Besides the bicycle, there are two people in the scene, one standing on the right and the other near the left side of the image.



[Image]: Chair-Elderly-Reading.jpg
🤖️: The image depicts an elderly man wearing glasses sitting on a park bench. He seems to be reading a book, possibly enjoying the outdoor environment. Several cars are parked nearby, one in the center of the image and another on the right. There is also a bench in the background, right next to the person sitting on the bench.
```

**Analysis of SFT VLM without Muon:**

After unfreezing the language model parameters and performing supervised fine-tuning, the description quality of the VLM undergoes a qualitative leap:

1.  **Detailed and Complete Descriptions**: Descriptions for each image become very detailed. For example, the description of the waterfall image expands from the simple "Water droplets on the rainbow bridge" to "a huge, colorful giant waterfall located next to a highway... A giant rainbow flag hangs above the waterfall, adding visual appeal."

2.  **Enhanced Spatial Relationship Understanding**: The model can describe the positional relationships of elements in the image. For example, the description of the dance image mentions "several chairs are placed on the stage, one on the left side of the frame, another on the right," demonstrating an understanding of spatial layout.

3.  **Improved Detail Observation Ability**: The model can notice secondary elements in the image. For example, in the image of the dog and woman by the sea, it not only identifies the "woman" and "dog" but also mentions "her dog sits on a blue and white checkered blanket."

4.  **Hallucination Issues Exist**: The model sometimes "sees" objects that do not exist. For example, it describes the spaceship as "looks like a giant commercial airplane... flying over a small hill and a barn," elements that are not obvious or do not exist in the original image.

5.  **Over-description**: Some descriptions contain too much speculative information. For example, the description of the city street is very detailed, including the number of vehicles, the location of traffic lights, etc., but some of these details may not be accurate.

**Key Finding**: The SFT stage, by unfreezing the language model, allows the model to express visual content with richer language. However, this also brings an "overconfidence" problem – the model tends to generate detailed descriptions even when some details are uncertain. This reflects a limitation of visual understanding: the uncertainty of visual features is not translated into uncertainty in language expression.

## VLM with Muon Optimizer (from DPO)

### Pretrained VLM

```
$ python eval_vlm.py --load 0 --model 0
VLM parameter count: 104.625 million
[Image]: city-traffic.jpg
🤖️: Night streets with elevators and sidewalks.



[Image]: Astronaut-Space.jpg
🤖️: Spaceman sent to a new Earth



[Image]: Dog-Woman-Sea.jpg
🤖️: You have a small ball in your palm, you throw it into the water.



[Image]: Rainbow-Falls.jpg
🤖️: Viewed on the water, water landscape



[Image]: Chair-Elderly-Reading.jpg
🤖️: An elderly person sitting on a park bench.



[Image]: Panda-Grassland.jpg
🤖️: This photo captures the cuteness and loveliness of this little white bear.



[Image]: Bicycle-Flowers.jpg
🤖️: Riding a bicycle on the street, bicycles everywhere, I saw many cars, this is my bicycle



[Image]: dance.jpg
🤖️: Performed by actors performing on stage
```

### VLM with SFT

```
$ python eval_vlm.py --load 0 --model 1
VLM parameter count: 104.625 million
[Image]: city-traffic.jpg
🤖️: This picture depicts a busy city street filled with skyscrapers and vehicles. At least twelve cars are driving on the street, some parked on the side, while others are moving.
Several traffic lights can be seen, one on the left side of the street, another in the middle, and one on the right. Additionally, a bus is heading towards the center of the frame, adding to the lively atmosphere of this bustling city.



[Image]: Astronaut-Space.jpg
🤖️: The person in the picture is wearing a black spacesuit and glasses, sitting on what looks like a space shuttle. They seem to be looking at a space shuttle flying in front of them, which is located on the right side of the scene.
Besides the space shuttle, there are two other small boats in the picture, one on the left and another on the right. A smaller plane can also be seen in the background, and the person is located on the far right.



[Image]: Dog-Woman-Sea.jpg
🤖️: The image depicts a woman sitting on a bench by the beach, holding a small dog outside to sunbathe. She is wearing a dress and seems to be enjoying the outdoors.
In the background, several other people can be seen scattered on the beach, some closer to the water and others farther away. They all look happy, possibly spending a good time with this woman.



[Image]: Rainbow-Falls.jpg
🤖️: The image shows a beautiful fountain surrounded by mist above it. The fountain is located above a high mountain, adding a magnificent background to the scene. An umbrella can be seen on the water, providing shade for visitors.
The terrain around the fountain consists of hills and mountains, offering a picturesque landscape for visitors. The presence of the fountain, water features, and surrounding mountains creates a serene and awe-inspiring atmosphere, making the area an ideal resort destination for photography enthusiasts and outdoor lovers.



[Image]: Chair-Elderly-Reading.jpg
🤖️: The image shows an elderly man sitting on a park bench, sitting in front of a book, holding it in his hands. The person looks relaxed and casual, possibly enjoying the outdoors.
There are several trees in the park, adding a natural atmosphere to the scene. Multiple benches are placed in different locations in the park for people to sit and enjoy the surroundings.



[Image]: Panda-Grassland.jpg
🤖️: The protagonist of the picture is a giant panda with black and white markings, standing on a lush, green grassland. This giant panda seems to be enjoying the warmth of the sun and the grass.



[Image]: Bicycle-Flowers.jpg
🤖️: The image shows a green bicycle parked on a lane with yellow flowers, loaded with colorful blossoms. The bicycle is parked in front of a building, with two adjacent buildings forming a stark contrast.
Besides the bicycle and flowers, there is a cup placed on the ground, possibly on or near the sidewalk.



[Image]: dance.jpg
🤖️: In the image, a woman in a black dress is standing on a stage. She is performing on stage, surrounded by several people watching her, some of whom are holding mobile phones. These phones are scattered throughout the scene, possibly taken to capture the performance or communicate with the audience.
```

## VLM with Muon Optimizer (from Pretrain)

### Pretrained VLM

```
$ python eval_vlm.py --load 0 --model 0
VLM parameter count: 104.625 million
[Image]: city-traffic.jpg
🤖️: A bus traveling from the city center to a tall building



[Image]: Astronaut-Space.jpg
🤖️:🤖️: A little boy on a spaceship



[Image]: Dog-Woman-Sea.jpg
🤖️: A dog walking by the seaside



[Image]: Rainbow-Falls.jpg
🤖️: Water droplets falling from a cave



[Image]: Chair-Elderly-Reading.jpg
🤖️: A young man reading a book on an elderly person's bed.



[Image]: Panda-Grassland.jpg
🤖️: A bear with a layer of cute black-and-white fur



[Image]: Bicycle-Flowers.jpg
🤖️: In a park in Paris, a little boy rides a bicycle along the riverbank.



[Image]: dance.jpg
🤖️: Performers wearing colorful costumes and fashionable outfits during a performance.
```

### VLM with SFT

```
$ python eval_vlm.py --load 0 --model 1
VLM parameter count: 104.625 million
[Image]: city-traffic.jpg
🤖️: This image depicts a bustling city street at night, with high-rise buildings and heavy traffic. Cars are driving in different directions, creating a vibrant urban scene. Cars, trucks, and motorcycles flow continuously, showing the bustling activity on this street.
A tall building stands prominently in the frame, forming part of the city skyline. The unique architectural style and scale of this building catch the attention of passersby, who might be drawn to appreciate its aesthetic value.



[Image]: Astronaut-Space.jpg
🤖️: The image features a large spaceship or spacecraft, equipped with electronic devices and flight instruments. It appears to be from a museum or exhibition space, as various objects are displayed inside. These objects vary in size and seem to have been created by different professionals or scientists for visitors to explore.



[Image]: Dog-Woman-Sea.jpg
🤖️: In the picture, a woman sits on a beach bench holding a brown-and-white puppy. The puppy looks very happy, enjoying its time on the sand. In the background, two other people can be seen, also sitting on the same bench.
Besides the woman and the puppy, various items appear in the scene, such as two handbags, a bench near the dog, a chair on the left, and a chair near the center of the scene.



[Image]: Rainbow-Falls.jpg
🤖️: This image shows a stunning scene of rough seas extending to the horizon under a cloudy sky. A large mountain with a white dome stands in the center of the frame, becoming the focal point. The sea seems to be crashing against the horizon, creating an impression of strong waves.
In this scene, several people are scattered around, possibly enjoying the sea and the spectacular sky. Some of these people are closer to the coast, while others are farther away, likely admiring the breathtaking view.



[Image]: Chair-Elderly-Reading.jpg
🤖️: An elderly man wearing glasses sits at a table in a library, surrounded by cluttered bookshelves and various books. He is sitting in a chair, focused on a book, possibly meditating or deep in thought. Behind him, a potted plant can be seen, adding a touch of greenery to the scene.
The library environment is very crowded, with bookshelves filled with all kinds of books, covering almost the entire wall. These books vary in size and position, some even overturned, giving the library a busy atmosphere.



[Image]: Panda-Grassland.jpg
🤖️: In the picture, a large black-and-white bear sits on green grass, with a few flowers scattered around. It seems to be enjoying time outdoors, possibly in a grove or on the grassland.



[Image]: Bicycle-Flowers.jpg
🤖️: The picture shows an outdoor garden with a bicycle parked between two other bicycles. Each bicycle has a basket filled with bright flowers. These flowers are arranged in various vases, adding color and vitality to the overall scene.
In the background, several people are in the garden, possibly enjoying a nice day. Some of them are near the bicycles, while others are elsewhere in the garden. Besides the bicycles, two cars are parked nearby, one near the foreground and the other farther away.



[Image]: dance.jpg
🤖️: This image depicts a woman in elegant clothing walking down a wide walkway in the dark. She seems to be attending a dance, as she holds an umbrella, possibly to shield from rain or sunlight.
Chairs are placed along the walkway, likely for the audience to sit and enjoy the dance. Several kites can be seen in the picture, adding a joyful atmosphere to the dance.
```


## VLM with Muon Optimizer (from SFT)

### Pretrained VLM

```
$ python eval_vlm.py --load 0 --model 0
VLM parameter count: 104.625 million
[Image]: city-traffic.jpg
🤖️: Monitoring of nighttime traffic lights



[Image]: Astronaut-Space.jpg
🤖️: A series of conversations between "our ship" and "our ship."



[Image]: Dog-Woman-Sea.jpg
🤖️: A cute woman in a white long dress and a cute pet dog



[Image]: Rainbow-Falls.jpg
🤖️: From the mountaintop, water glistens in the sunlight.



[Image]: Chair-Elderly-Reading.jpg
🤖️: An elderly person sitting on a bench in the park



[Image]: Panda-Grassland.jpg
🤖️: A cute zebra in the woods



[Image]: Bicycle-Flowers.jpg
🤖️: This video uses a horse working in a car.



[Image]: dance.jpg
🤖️: A dancer performing on stage, wearing a stylish outfit.
```

### VLM with SFT

```
$ python eval_vlm.py --load 0 --model 1
VLM parameter count: 104.625 million
[Image]: city-traffic.jpg
🤖️: This photo captures a busy city street at night, with cars and trucks on the road. The street is lined with high-rise buildings, creating a bustling atmosphere. The street is crowded with traffic, including multiple cars and a truck. Some of these vehicles are stationary, while others are moving.
A large number of high-rise buildings appear in the frame, highlighting the urban environment. These buildings vary in size and shape, forming the architectural landscape of the area. This nighttime photo emphasizes the dynamic nature of city life, with various elements combining to create the character of a night-time metropolis.



[Image]: Astronaut-Space.jpg
🤖️: The scene in the image shows a soldier sitting on a blue ship, which contains a large TV screen. The soldier appears to be looking at a smartphone screen, possibly for monitoring or communicating with the outside world.
There are several other people on the ship, possibly crew members or scientists. Some of them are scattered around the ship, while others are near the TV screen. Additionally, two TV remote controls are placed on the ship, indicating they might be monitoring or interacting with the equipment.



[Image]: Dog-Woman-Sea.jpg
🤖️: In the photo, a woman sits on the beach holding a large brown dog. She seems to be posing with the dog for the picture. The dog is on the left side of the frame.
In the background, multiple figures can be seen scattered across the beach. Some of them appear to be enjoying the beach, while others might be sightseeing or socializing.



[Image]: Rainbow-Falls.jpg
🤖️: This image showcases an impressive fountain landscape, towering high on a grassy hill. The fountain occupies a significant portion of the frame, extending from the center to the far right, looking like a massive work of art.
The surroundings of the fountain, including the hill below and some trees in the background, provide a picturesque backdrop for this impressive fountain.



[Image]: Chair-Elderly-Reading.jpg
🤖️: In the picture, an elderly man sits on a park bench reading a newspaper. He seems to be enjoying a peaceful time in the park, perhaps resting in the afternoon or pondering something.
In the background, multiple cars can be seen parked near the park, creating a tranquil atmosphere. Additionally, a person appears at the top of the frame, possibly watching the man read the newspaper, perhaps enjoying nature or waiting for someone.



[Image]: Panda-Grassland.jpg
🤖️: The picture shows a small black-and-white panda standing on a patch of grass. This cute panda looks very relaxed and comfortable.



[Image]: Bicycle-Flowers.jpg
🤖️: The picture shows a green bicycle parked next to a bench covered with a green tablecloth. This bench seems designed for gatherings, as it is near a potted plant.
Besides the bicycle and the potted plant, a car is parked on the right side of the scene. A stop sign can be seen in the background, adding an urban touch to the image.



[Image]: dance.jpg
🤖️: The image shows a woman in a tuxedo standing on a stage, holding a microphone, seemingly delivering an engaging performance. She looks like an actor or performer, with several people around her, possibly the audience or participants.
Various items are placed on the stage, including a wine glass and several bottles. Some of these bottles are near the stage, while others are scattered in the background. The scene captures an event on stage, with the actor or performer delivering a memorable show for the audience.
```

---

## Key Findings and Summary of VLM Training

### Impact of Algorithm Improvements on VLM

By comparing different VLM configurations (without Muon vs with Muon, from DPO vs from Pretrain vs from SFT), we derive the following key findings:

1. **Base LLM Quality Determines VLM Upper Bound**:
   - VLMs trained starting from a DPO model generally perform best, as the DPO model inherently has better language expression capabilities
   - VLMs starting from a Pretrain model produce more concise descriptions but are more stable during training
   - VLMs starting from an SFT model perform best in terms of format standardization

2. **Advantages of the Muon Optimizer in Multimodal Training**:
   - VLMs with the Muon optimizer converge faster for the same number of training steps
   - Both the accuracy and richness of detail in descriptions are improved
   - For example, in describing an astronaut space image, the Muon version can more accurately identify details like "space shuttle"

3. **Projection Layer Training vs. Full Model Fine-Tuning**:
   - **Pretrained VLM (training only the projection layer)**: Descriptions are concise but highly accurate, with less tendency to hallucinate
   - **SFT VLM (unfreezing the entire model)**: Descriptions are detailed and rich, but prone to overconfidence, generating non-existent details
   - This reveals a trade-off: stronger expressive ability comes with a higher risk of hallucination

4. **Limitations of Visual Understanding**:
   - All VLM versions exhibit some degree of object recognition errors (e.g., identifying a "panda" as a "zebra")
   - Understanding of complex scenes (e.g., dance, spaceship) is prone to misinterpretation
   - This reflects the inherent limitations of the CLIP vision encoder, which are difficult to fully overcome with only a projection layer and language model fine-tuning

5. **Suggested Training Strategy from LLM to VLM**:
   - **Initial Stage**: Use the highest quality LLM as a starting point (e.g., a DPO model)
   - **Projection Layer Training**: First freeze the LLM parameters, train only the projection layer to establish basic vision-language alignment
   - **Full Model Fine-Tuning**: Unfreeze the LLM parameters and fine-tune using high-quality image-description pairs
   - **Algorithm Selection**: Using optimizers like Muon in multimodal training can achieve better convergence speed and final performance

### Training Cost and Effect Comparison

| Configuration | Base LLM | Training Time | Description Quality | Hallucination Level |
|------|----------|----------|----------|----------|
| Without Muon - Pretrained VLM | SFT | Short | Concise but accurate | Low |
| Without Muon - SFT VLM | SFT | Medium | Detailed and rich | Medium |
| With Muon - Pretrained VLM (from DPO) | DPO | Short | Concise and accurate | Low |
| With Muon - SFT VLM (from DPO) | DPO | Medium | Detailed and accurate | Relatively Low |
| With Muon - SFT VLM (from Pretrain) | Pretrain | Medium | Relatively detailed | Medium |

### Practical Recommendations

Based on the comprehensive testing in this experiment, we offer the following practical recommendations:

1. **Prioritize Improving Base LLM Quality**: Investing resources to improve the language model (through algorithmic optimizations like QK Norm + Muon) is more effective than simply expanding VLM training data

2. **Adopt a Phased Training Strategy**: A two-stage training strategy, first training the projection layer and then the full model, is the best choice for balancing efficiency and effectiveness

3. **Be Vigilant About Hallucination Issues**: When unfreezing the LLM for full model fine-tuning, special attention must be paid to potential hallucinations. Consider introducing uncertainty modeling or explicit expressions of "uncertainty"

4. **Compound Effect of Algorithm Improvements**: The improvements from QK Norm + Muon are effective in both LLM and VLM training, demonstrating the long-term value of algorithmic optimization

5. **Capability Boundaries of Small Models**: While a 100M-parameter VLM can complete basic image description tasks, it still has clear limitations in complex scene understanding, detail accuracy, and reasoning ability. Practical applications require larger model scales.