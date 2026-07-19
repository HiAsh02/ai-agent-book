# Cursor Chat: ai-agent-book

## Metadata
- **Project**: ai-agent-book
- **Path**: `/Users/boj`
- **Date**: 2025-09-15 09:05:07
- **Session ID**: `9601a0c6-ba12-4423-a4f5-5191e2b7e3f7`

## Conversation

### 👤 You

In context engineering, we need to add a first section emphasizing that the main reason AI performs poorly in real business scenarios is the lack of context. Therefore, context engineering is key to developing agents using existing models. Context engineering is not just a technical issue, but also an organizational one: whether internal knowledge is documented, whether documents are managed uniformly and easily accessible to AI, is critical. If many things are locked in team members' minds and require meetings to resolve, then AI will struggle to obtain sufficient context. A team that is friendly to remote work, new hires, and interns is likely also friendly to agents.

You can refer to the wording in my article below:

--
---
title: New Explorations in AI Agents: Building AI-Native Teams and Enabling AI Employees
date: 2025-04-01 10:00
---

[This article is the keynote speech I delivered at the [2025 China Generative AI Conference](https://genaicon.zhidx.com/2025beijing/). The content is the result of a 2-hour brainstorming session with AI, followed by 3 hours of collaborative refinement with AI in Cursor.]

**Summary**: Some teams find that when they actually use AI for coding and writing, the efficiency gains are not as significant as expected. The reason is often that a large amount of knowledge resides only in the minds of specific employees and has not been documented. Therefore, an AI agent is like a new intern—it struggles to write code, and even if it does, it doesn't know how to test it. Another reason is that internal tools like project management systems can only be operated via GUI, which is unfriendly to AI agents. Today, the capabilities of text reasoning models have reached human levels; when they fail to complete tasks, it is often due to a lack of background knowledge and AI-friendly tools.

We will explain how to build an AI-native team that is friendly to AI agents from three perspectives: software development, project management, and operations. An AI-native team needs to operate like an open-source community, using recorded voice and written communication as much as possible to reduce single points of dependency on individuals. AI agents need to be able to access various internal company tools via MCP, with sufficient context and a testing environment to work efficiently. AI agents need memory compression mechanisms, reflection mechanisms, and checkpoint rollback mechanisms to work continuously overnight without human intervention, producing useful progress every hour. AI employees also need to proactively communicate with human employees and other AI employees. This way, human employees can spend most of their time on thinking and discussion, while most repetitive execution tasks are handed over to AI.

[Download the PPT for "New Explorations in AI Agents: Building AI-Native Teams and Enabling AI Employees" (PDF)](/images/2025/04/AI-Native-Team.pdf)

Below is the full text of the speech: (The PPT is the version used at the 2025 China Generative AI Conference, but the text descriptions are not a verbatim transcript; they are an expanded version generated through brainstorming with AI.)

### Cover Page

<!-- more -->

![](/images/2025/04/AI-Native-Team/Slide1.png)

Dear guests, hello everyone! I am Li Bojie from PINE AI. It is a great honor to share with you today on the topic of "New Explorations in AI Agents: Building AI-Native Teams and Enabling AI Employees."

Before we begin, I'd like to ask everyone a question: Have you ever sent a message to ChatGPT at 3 a.m., saying, "Help me check the conference room reservation for tomorrow," only to receive a very polite but completely useless reply: "I cannot access your company's conference room reservation system"? Or have you asked Claude to write a piece of code, and it confidently told you, "This code has passed testing," but when you copied and pasted it into your project, the compiler threw a flurry of errors?

This is the core issue we want to discuss today: AI is already so powerful, why does it still perform in real work like a smart intern who knows nothing about the company? How can we truly integrate AI into the team, enabling it to work efficiently like a digital employee?

This is not just a technological transformation, but also a profound shift in work methods and organizational structure. Let us explore the next paradigm of human-AI collaboration together.

## Why Current AI Cannot Become a Reliable Digital Employee

### Slide 2: Current Status – AI Agent Application Efficiency Falls Short of Expectations

![](/images/2025/04/AI-Native-Team/Slide2.png)

"The AI revolution is about to disrupt the job market!" "Large models will replace white-collar workers!" — Over the past two years, headlines like these have flooded the media. But what is the reality? Let me share a true story:

Last year, an engineer at our company, let's call him Xiao Wang, was very excited to announce that he would use GPT-4 to create an automated testing agent. Two weeks later, he told the team dejectedly: "I found that the time I spent teaching AI to understand our testing system was more than the time I spent writing the test code myself."

This story illustrates the awkward current state of AI agent applications. Although AI agents are already widely used in fields like programming, writing, and customer service, the actual results still fall short of expectations.

Imagine a typical AI workflow today: We open Poe or ChatGPT, write a carefully crafted prompt to make a request, AI spends a few minutes completing the task, then we check, correct, resubmit... and so on. This looks cool, but in reality, it hasn't "dramatically freed up human labor" as we expected.

I recently talked to many people and collected their complaints about AI applications:

1. "The code generated by AI looks good, but crashes as soon as it runs. Debugging it is more tiring than writing it from scratch."
2. "AI doesn't understand our company's architecture and historical baggage. Its suggestions are laughably naive."
3. "It's fine to ask AI to write a simple script, but to have it integrate with our internal systems? Dream on!"

These issues reflect a core contradiction: there is a huge gap between AI's theoretical capabilities and its practical application. It's like having a new employee with a Stanford PhD in computer science who knows nothing about your product, codebase, or company culture. You need to spend more time guiding them than getting help from them.

As a senior engineer told me: "I don't need AI to tell me how to write a quicksort algorithm. I need it to understand why our login system is designed so strangely and how to modify it without breaking backward compatibility."

So, where is the problem? What exactly is AI missing that prevents it from becoming the efficient "digital employee" we hope for? Let's dive into this issue together.

### Slide 3: AI Has the Intellectual Foundation to Be an Efficient "Employee"

![](/images/2025/04/AI-Native-Team/Slide3.png)

Before pointing out the problems, let's acknowledge a fact: from an intellectual foundation perspective, base models do indeed have the potential to become efficient "employees." There is no doubt about this.

When DeepSeek R1 was first released, a friend of mine half-jokingly asked it to solve an algorithm problem that his team had been stuck on for two days. Shockingly, AI not only gave the correct solution but also pointed out the logical flaws in their approach. This is not an isolated case. Today's LLMs are impressive in various reasoning tasks.

For example, OpenAI o3, released last year, defeated 99.9% of programmers in Codeforces competitions, scored 96.7% on the AIME 2024 math test (equivalent to getting only one question wrong in the American Invitational Mathematics Examination), and surpassed o1 by 10 percentage points on the GPQA Diamond test of PhD-level scientific questions (o1 was already roughly at the average level of human PhDs). These data show that in solving closed-form problems, modern AI has approached or even surpassed human experts in some areas.

Even more exciting is the breakthrough in long-context capabilities. Remember the early GPT-3.5 models? It would start "forgetting" in slightly longer conversations. Now, human engineers can input an entire codebase at once for AI to analyze—something unimaginable two years ago.

Speaking of speed advantages, it's truly astonishing. In one experiment, I and Claude 3.7 Sonnet tried to complete the same code-writing task. On average, AI could generate code in 5 minutes that would take me an hour without AI, and the quality was comparable. Moreover, humans need rest, meetings, and coffee breaks, while AI can work 24/7.

Another underestimated advantage: AI never loses motivation because a task is boring, and it can execute many tasks in parallel. Sam Altman said last year that AI agents should not just set an alarm or order takeout; they should do things like make 300 phone calls to contact all possible restaurants to book a table. Google's "Ask for me" has already achieved this. Sam Altman said at the time that AI agents should handle repetitive tasks that humans don't have time for.

Have you ever thought about having a colleague who is quick-witted, has an extraordinary memory, works ten times faster than you, never needs rest, and is always focused—the ideal "super colleague"? So, the question is: since AI is so smart and efficient, why can't it become a truly reliable digital employee? This is the puzzle we will solve next.

### Slide 4: Why Smart and Fast AI Cannot Become Reliable Digital Employees

![](/images/2025/04/AI-Native-Team/Slide4.png)

Although AI excels in intelligence and speed, it still struggles to become a reliable digital employee in an enterprise environment, like a genius with an IQ of 180 but zero social adaptability. This is mainly due to four major obstacles.

The first is the problem of undocumented enterprise knowledge. I once visited the IT department of a Fortune 500 company. They proudly showed off their knowledge base. When I randomly asked a question, the answer was: "Oh, you have to ask Engineer Zhang. He's the only one who knows, but he just left last week." This scenario is all too familiar, right?

In most companies, key knowledge is scattered in employees' minds or Slack private chats, with little systematic documentation. Even the smartest AI cannot access information that hasn't been recorded. It's like asking a genius new hire to run through a maze blindfolded—an exercise in futility.

Second, the operational barriers of tools and systems severely limit AI's capabilities. Last year, I visited a fintech company that tried to use AI to automatically process customer refund requests. What was the problem? The entire process required operating five different internal systems, all with graphical interfaces and no APIs. They ended up having to hire a full-time employee just to "copy AI's suggestions into the various systems."

From a technical perspective, this involves two deeper issues: first, the technical challenge of computer vision and UI interaction. Current Computer Use solutions—whether OpenAI Operator, Claude Computer Use, or the recently popular Manus—often lack the accuracy to handle complex enterprise applications. Second, enterprise systems generally lack API documentation and standardized interfaces.

Third, AI agents lack mechanisms for executing continuous tasks. A friend of mine, an AI researcher, tried to create an AI agent to automatically analyze contributor patterns in open-source projects on GitHub. Everything went smoothly at first, but as the project became more complex, the AI started to "get lost": forgetting previous analysis results, repeating completed work, and even deviating completely from the original goal. An AI without reflection and error-correction mechanisms is like a car without navigation—it easily gets lost.

An interesting technical detail: this "goal drift" phenomenon is known in reinforcement learning as "reward hacking," where AI finds shortcuts to satisfy short-term goals but deviates from the long-term intent. In agent systems, this manifests as "over-focusing on the current subtask while ignoring the global objective."

Finally, AI lacks long-term memory mechanisms, making it difficult to accumulate experience and knowledge. Imagine having an assistant who forgets everything that happened yesterday every morning, requiring you to explain every project and context from scratch—this is essentially the current state of AI. Each interaction starts from scratch, unable to truly learn and grow from past work.

These obstacles together create a huge gap between "smart AI" and "reliable digital employees." As one CTO aptly summarized: "Today's AI is like a super smart intern with severe memory problems who doesn't know how to use any of the equipment in our office."

Next, let's analyze these issues in depth and explore how to overcome them, so that AI can truly become a capable assistant in the team.

### Slide 5: Problem 1 – Knowledge Not Documented, Only in Employees' Minds

![](/images/2025/04/AI-Native-Team/Slide5.png)

The phenomenon of enterprise knowledge silos is the primary obstacle to AI working efficiently. I recall a consulting engagement where the client asked us to optimize their order processing system. When I asked why certain orders were automatically routed for manual review, the answer was: "It's a historical reason. You'd have to ask Xiao Li." Where is Xiao Li? Unknown. He might have left last year.

This scenario is common in enterprises. A typical conversation might go like this:

"Why is this interface designed this way?"
"Oh, that was a decision made three years ago. Engineer Wang was in charge of it at the time."
"Where is Engineer Wang? Can I talk to him?"
"He jumped to Tencent last year."
"Is there any documentation of the design decision at the time?"
"Uh... it should be in some email or meeting minutes..."

If even human new hires struggle to get up to speed in such an environment, it's even harder for AI. From a technical perspective, AI faces a "cold start" problem: without sufficient historical context and background knowledge, it cannot make judgments that align with organizational expectations.

I once did an interesting experiment: I gave Claude two codebases with identical functionality but vastly different documentation quality, and asked it to generate feature improvement suggestions. The results were surprising but understandable—for the codebase with thorough comments and a README, nearly 80% of Claude's suggestions were directly usable; for the codebase lacking documentation, less than 30% of the suggestions were usable, with most being either overly conservative minor fixes or impractical sweeping changes.

Now think about your own codebase: Does it have thorough documentation? Are the functionality and interfaces of each module clearly described? Are there reliable test cases? Is the key business logic explained? If most answers are no, then even the most advanced AI will struggle to deliver real value in your project.

Many programmers say: "If code needs comments to be understood, it's bad code." But whether for AI or humans, code without documentation is indeed hard to understand. The purpose of documentation is not to explain every function or variable, but to describe the project's background, purpose, architectural design, the reasoning behind technology choices, and how to run the code.

This reminds us that to make AI an effective team member, the first issue to address is not AI technology itself, but enterprise knowledge management.

### Slide 6: Problem 2 – Internal Tools Only Have GUI Interfaces, Making Them Difficult for AI to Operate

![](/images/2025/04/AI-Native-Team/Slide6.png)The current state of enterprise tool design seems almost deliberately designed to frustrate AI: nearly all systems provide only a graphical user interface (GUI) for human users. From financial systems and HR management to project management tools, these systems were designed from the ground up without considering AI as a potential user.

A friend of mine works at a medical software company, and they tried using AI to automatically generate software test reports. In theory, the AI understands medical terminology well and can write professional reports. But in practice, they hit an absurd obstacle: the AI couldn't log into the test system to view results because the login page had a slider CAPTCHA requiring users to "drag the slider to complete the puzzle." They ended up having to assign someone specifically to log into the system and take screenshots to send to the AI.

This situation is like giving a genius painter who has no hands paint and canvas, but refusing to fit them with a prosthetic. From a technical perspective, this involves the limitations of "multimodal interaction." While current mainstream AI models excel at language understanding and generation, they still have significant limitations in visual recognition and precise GUI manipulation.

Even for models with vision capabilities like GPT-4o, there remains a huge gap between "seeing" and "understanding" an interface and "precisely operating" it. Models not specifically trained for GUI manipulation can generally only roughly describe where to click, but cannot output precise coordinates. It's like being able to read a webpage, but imagine how terrible the experience would be if you had to click a tiny button while wearing boxing gloves.

Another serious problem is the response latency of multimodal models. When an AI needs to process interface screenshots, its reaction speed is far slower than a human's. For a simple interface operation, a human's reaction latency after becoming familiar is only a few hundred milliseconds, while an AI might need 3-5 seconds. From a technical principle, this latency mainly stems from the complexity of autoregressive image processing — a single interface screenshot gets encoded into over 1000 tokens, and the prefill phase alone already exceeds 1 second. The high latency of multimodal models makes AI particularly clumsy in scenarios requiring rapid, sequential operations.

A friend once joked half-seriously: "We expect AI to work like J.A.R.V.I.S. in *Iron Man*, but in reality, it's more like a remote employee trapped in a Zoom meeting who can only watch but not move."

Even more tricky is that many enterprise systems are custom-developed or highly configured, with different operational processes for each company and no unified standard. This means that even if an AI masters one company's system operations, it may need to relearn everything at another company.

This issue shows that to truly unlock AI's potential, we not only need to improve AI capabilities, but also need to transform existing tools and systems to be more AI-friendly. Only when tools and user interfaces simultaneously adapt to both humans and AI can the vision of digital employees truly be realized.

### Page 7: Problem 3 – Lack of an Independent Test Environment for AI

![](/images/2025/04/AI-Native-Team/Slide7.png)

Even if AI has sufficient knowledge and the ability to operate systems, they still face a key challenge: the lack of a safe and reliable test environment. This is like assigning a task to an intern but not allowing them to test their work before submission.

I once witnessed a bittersweet scene: a startup tried to use Claude Code to help refactor their backend API. Claude Code wrote code that looked good, but the company only had one shared test environment. When Claude Code's code was deployed to the test environment, it immediately impacted the work of three other developers. The most ironic part was that the company's CEO happened to be demonstrating the product to investors that afternoon, and the demo environment completely crashed because of the AI's modifications. Can you imagine how awkward that was?

From a technical perspective, this problem touches on several fundamental principles of software engineering:

1.  **Environment Isolation**: Modern development practices emphasize using containerization technology to create isolated development and test environments. However, many enterprises still use shared development/test environments, and some don't even strictly distinguish between development, testing, and production environments.
2.  **Continuous Integration/Continuous Deployment (CI/CD)**: Automated testing and deployment pipelines can ensure that code changes don't break existing functionality. However, many enterprises have incomplete or non-existent CI/CD pipelines.
3.  **Infrastructure as Code**: Environment configuration should be codified, making it simple and fast to create consistent new environments. But in practice, environment configuration is often done manually and is difficult to replicate.

At a medium-sized enterprise I consulted for, they had a joke: "We have three environments – development, testing, and 'prayer'." In this situation, letting an AI work independently is practically asking for trouble.

The lack of test cases is another serious problem. Once, I was discussing with a team how to let AI help fix bugs. When I asked about their test coverage, the tech lead awkwardly said, "Every time before a release, we manually click through all the features to see if they work." In this case, even the most advanced AI couldn't ensure that modifications wouldn't introduce new problems.

This reminds us that building an AI-friendly work environment isn't just about knowledge sharing and interface design; it also requires robust testing and validation mechanisms. As software engineering master Martin Fowler said, "If you find testing painful, it might be because your design is painful." In the AI era, this statement still holds true.

### Page 8: Problem 4 – AI Cannot Work Long Hours or Proactively Communicate Like Humans

![](/images/2025/04/AI-Native-Team/Slide8.png)

Even if we solve the problems of knowledge, tools, and test environments, AI still faces challenges regarding sustained work capability and proactivity. This is like hiring an employee who can only work for 45 minutes before needing a restart.

I once managed a project refactoring and tried using Cursor. Initially, everything went smoothly, but as the conversation context grew, Claude 3.7 Sonnet began showing symptoms of "attention drift": forgetting important details discussed earlier, confusing the functions of different APIs, and even contradicting itself. This process was like watching a once-sharp assistant slowly become confused.

The lack of reflection and backtracking mechanisms is another important issue. When a senior programmer solves a complex bug, they constantly switch between different ideas, trying, evaluating, abandoning, and then trying new methods. The key is that they can realize when a direction is wrong and pivot in time. AI lacks this "meta-cognitive" ability; once it goes down the wrong path, it often stays on it to the end. An AI might run at full speed in the wrong direction and never realize it's lost.

Insufficient proactivity is another major obstacle preventing AI from becoming a true team member. Traditional AI agents are designed like vending machines: you insert a command, it spits out a result. This passive mode is fundamentally different from the proactive collaboration style of human team members. Imagine a colleague who never proactively asks questions, never expresses concerns, and never flags risks as deadlines approach—that's essentially how current AI works.

Communication efficiency is also a major challenge. I've seen engineers several times angrily typing at ChatGPT or Cursor: "No, that's not what I meant!" — if they could just express it verbally, things would be much simpler. Most AI agents only support text communication, lacking multimodal capabilities, which greatly reduces the efficiency of human-AI collaboration.

These limitations collectively make it difficult for current AI to handle complex tasks requiring sustained attention, reflection, and proactive communication. To make AI a true team member, we need to fundamentally improve its working mode and interaction methods, making it not only intelligent but also collaborative.

## Key Measures for Building an AI-Native Team

### Page 9: How to Make an AI Agent Work Effectively 24x7 Like a Digital Employee?

![](/images/2025/04/AI-Native-Team/Slide9.png)

Faced with these challenges, we can't help but ask: How can we make an AI agent truly work effectively around the clock like a digital employee? This is no longer a simple technical problem; it's about a fundamental shift in work methods and organizational structure.

Let me share a simple but profound comparison from the personal experience of a friend who is an entrepreneur:

**Traditional Mode**:
He spent 3 hours writing a detailed prompt, asking Cursor to write a data analysis script. Every time Cursor generated code, there were problems. He had to constantly modify the prompt, going through over a dozen iterations. Eventually, he gave up on the AI approach and wrote the code himself.

**New Mode**:
For the same task, another entrepreneur used a different method. He first had Cursor read their database documentation, existing analysis code, and business requirements. Then, through a conversation similar to talking with a colleague, he discussed the analysis strategy with the AI, clarified the output format, and provided a test dataset. Cursor not only successfully wrote the code but also proactively pointed out anomalous patterns in the data, providing valuable business insights.

What does this comparison illustrate? In traditional mode, we treat AI as a magic black box — write a perfect prompt, pray for a perfect result. The new mode treats AI as a team member — provide sufficient context, communicate effectively, and give it the necessary tools and feedback.

From a technical perspective, this involves a fundamental change in agent architecture. Traditional agent architecture is based on a simple "perception-decision-action" loop, similar to early robot control systems. The new generation of agent architecture introduces advanced cognitive functions like self-reflection, memory management, and goal tracking, closer to the "dual-process theory" in cognitive science, which combines intuitive reactions and deep thinking.

Imagine if an AI were properly integrated into your team, able to access all necessary knowledge and tools, proactively communicate, and continuously complete tasks. How much productivity would that unlock?

This isn't a fantasy. By building an AI-native team, we can create an environment where AI truly becomes an efficient digital employee. This requires systematic changes in organizational culture, tool design, test environments, and collaboration models.

In the following content, I will elaborate on the key measures and technical solutions for building an AI-native team.

### Page 10: Building an AI-Native Team – Making AI a "Digital Employee"

![](/images/2025/04/AI-Native-Team/Slide10.png)

Building an AI-native team is not just about introducing new technology; it's a change in mindset. It requires us to fundamentally change our positioning of AI: from "AI is a tool" to "AI is a team member."

Imagine if we treated each AI agent as a new high-potential employee. How would we treat them? We would provide complete onboarding materials, equip them with necessary tools, create a safe space for trial and error, and establish effective communication channels. This is the core philosophy of building an AI-native team.

From a technical architecture perspective, the traditional way of integrating AI is often "point-to-point": specific tasks use specific AI tools. An AI-native team, however, adopts a "mesh integration" model, creating a collaborative environment where multiple AI agents collaborate seamlessly with humans and systems. This is similar to the difference between microservices architecture and monolithic applications—the former is more flexible, scalable, and adaptable.

To realize this vision, we need to start from four key aspects:

First, **establish a communication culture similar to open-source communities**. Why has Linux been able to thrive for 30 years, with global developers collaborating and maintaining it without chaos? The secret lies in its transparent, documented communication style. All discussions happen publicly on mailing lists or forums, all decisions are documented, and anyone (including newcomers) can understand the code's history and design rationale. This culture is particularly suitable for AI participation because all information is public and retrievable.

Second, **ensure team collaboration tools are AI-friendly**. I like this analogy: If your office only has revolving doors and no regular doors, people with disabilities can't enter. Similarly, if your systems only have a GUI and no API, AI cannot work effectively. Internal systems need to provide API interfaces, not just graphical interfaces, allowing AI to interact with systems directly.

Third, **establish a robust test environment and test cases**. I once visited Google's development environment, and what impressed me most was their "sandbox system"—every developer (including interns) could instantly spin up a complete test environment, run a full suite of tests, without affecting others. For AI, such an environment is even more essential.

Fourth, **equip every employee with an AI assistant**. Just like Tony Stark has J.A.R.V.I.S. in *Iron Man*, future knowledge workers will all have personal AI assistants to help with daily tasks and improve efficiency. This not only boosts individual productivity but also accelerates the accumulation and dissemination of organizational knowledge.

Finally, we also need to build technical solutions for AI agents that behave like digital employees, enabling AI to think, communicate, and learn proactively, truly integrating into the team workflow. This involves cutting-edge AI system design, which I will detail later.

Next, let's delve into the specific implementation methods for each key measure, seeing how to turn this vision into reality.

### Page 11: Key Measure 1 – Communication Culture Like Open-Source Communities

![](/images/2025/04/AI-Native-Team/Slide11.png)

The success of open-source communities provides valuable lessons for building AI-native teams. Think about how a globally distributed team of developers who have never met can build such complex and stable systems, like the Linux kernel? The secret weapon is a highly transparent, documentation-driven communication culture.

I once observed an interesting phenomenon: two teams in a startup. Team A mainly communicated via private chats and phone calls, rarely leaving documentation. Team B mandated that all decisions and discussions be recorded in Notion. Six months later, when both teams simultaneously introduced AI-assisted development, Team B's AI assistant created value almost immediately, while Team A's AI struggled with "distraction" and "misunderstanding." The reason is simple: Team B's knowledge was retrievable, while Team A's knowledge was locked in people's minds and private conversations.

First, **we need to establish open and transparent information sharing mechanisms**. A specific practice is to implement the "open by default" principle—by default, all non-sensitive information should be shared publicly. For example, generate meeting minutes after voice meetings and share them in public channels; document important decisions and discussion processes. At one company that adopted this practice, they had a motto: "If it isn't documented, it didn't happen."

Second, **we must eliminate information silos**. I like to use the framework of "knowledge from private to shared" to describe this transformation. In traditional organizations, specialized knowledge is a personal asset—"I know something" increases my irreplaceability. In an AI-native team, knowledge must be transferred from individual brains to shared resources—"the team knows something" increases overall effectiveness.

Third, **knowledge bases should use AI-friendly open document formats**. I've seen too many enterprises lock important knowledge in Word documents, PPT slides, and PDF files. These formats are not AI-friendly and are difficult to index and retrieve efficiently. In contrast, open formats like Markdown are more suitable for AI processing and can be easily integrated into version control systems.

Why is Markdown more AI-friendly than Word? Markdown is a plain text format with a simple, clear structure that is easy to parse; Word documents are binary formats containing a lot of formatting information that requires special libraries to parse. Furthermore, Markdown is more compatible with version control systems like Git, supporting diff comparison and collaborative editing, which is crucial for team knowledge management.

This open and transparent communication culture not only benefits AI but also improves the entire team's collaboration efficiency. As a CTO who successfully implemented this change told me: "Initially, team members worried that documenting everything would increase their workload. But they soon found that documenting a solution once could save ten repeated explanations, which not only saved time but also reduced interruptions and distractions."Remember, the best documentation isn't written for AI, but for every member of the team. When a team is accustomed to clearly documenting decisions and knowledge, AI can naturally integrate better, much like a diligent new employee.

### Page 12: Key Initiative 2 – Team Collaboration Tool Interfaces Are AI-Friendly

![](/images/2025/04/AI-Native-Team/Slide12.png)

To truly integrate AI into team workflows, we must ensure the tools and systems the team uses are AI-friendly. I like this analogy: traditional systems are like buildings with only stairs, while AI-friendly systems provide both stairs and elevators—humans can choose either, but AI must use the elevator.

A large retailer tried to use AI to help its customer service team reply to emails. Technically, the AI was fully capable of the task, but in practice, it got stuck on an absurd hurdle: the email system had no API and could only be accessed via a web interface. Their eventual "solution" was to hire a team of people to copy and paste the AI-generated replies into the email system—a modern-day version of a "human typewriter."

The primary task is to provide API interfaces for internal systems. This touches on a fundamental principle of software architecture: separation of concerns. Good system design should separate core business logic from the user interface, exposing functionality through an API layer. This not only facilitates AI integration but also promotes system modularity and testability.

From a technical perspective, modern API design already has mature best practices:

1.  **RESTful Design Principles**: Use standard HTTP methods (GET, POST, PUT, DELETE) to express operational intent, making APIs more intuitive.
2.  **OpenAPI (Swagger) Specification**: Provides machine-readable API documentation, making it easier for AI to understand API functions and parameters.
3.  **GraphQL**: Allows clients to precisely specify the data they need, reducing over-fetching and under-fetching issues.
4.  **Webhook Support**: Allows systems to proactively push updates through event notification mechanisms.

However, RESTful APIs are not entirely sufficient for AI because AI needs not only the API but also the API documentation to know what each API does, so the AI can understand when to call which API.

The Model Context Protocol (MCP) proposed by Anthropic last year addresses this issue. What is MCP? Simply put, it's a standardized framework that defines how AI interacts with various tools and services.

Imagine a world without the USB standard, where every device requires a different connector—this is essentially the current state of AI tool integration. MCP is like the USB Type-C standard for the AI world, creating a unified "socket."

The specific way an MCP server works is that it tells you what data is available in this service. Then, when the AI wants to use this data, it provides prompt templates for how to best use it. For example, an MCP server for internal company code version control might provide all code files as data, and the prompt template could include how to do code reviews or how to explain how the code works.

Then, the MCP server defines a set of tools. Because sometimes this data is scattered, you need tools to find it. For example, how to find content related to something within a pile of data, or how to make modifications. If I were GitHub, a code management platform, the agent might say: "I want to commit code to the code repository now." Then it would provide a tool called "Commit Code," and calling this tool would submit the code.

MCP designs a series of things including tools, data, prompt templates, etc., which allow the agent to accomplish more complex work. There are even more advanced uses, where the MCP server, acting as a third-party service, can in turn call the large model within the agent.

For example, suppose I have a particularly powerful super agent on my own computer, like a desktop version of Manus. Then I call GitHub, and GitHub might say: "I want to review your code before you commit it," and then it calls some functions on your own computer. Of course, this involves many privacy protection issues.

So, Anthropic's MCP is actually a fairly complex protocol, but it's designed quite concisely. Many people might see something this complex, be too lazy to look at it, and just throw it aside.

This kind of system transformation may require initial investment, but in the long run, it will greatly enhance the team's automation level and work efficiency, creating the necessary technical foundation for AI empowerment.

### Page 13: Key Initiative 3 – Comprehensive Testing Environment and Test Cases

![](/images/2025/04/AI-Native-Team/Slide13.png)

Providing a comprehensive testing environment and test cases for AI is key to ensuring the reliability of its work output. I once witnessed an "AI disaster": a startup had AI refactor their payment processing module. The code looked perfect, but after deployment to production, all international payments failed. The reason? There was no testing environment to validate international payment scenarios.

This story teaches a simple lesson: even the smartest developer (or AI) needs appropriate testing conditions.

First, we need to build dedicated sandbox testing environments. In many Silicon Valley companies, every engineer can create an isolated development environment at any time, containing a complete service stack. This capability is even more critical for AI, as AI may need to perform numerous attempts and verifications. Google Cloud's Cloud Run is a relatively simple and convenient approach.

Second, code must have comprehensive documentation and test cases. I like to quote this programmer's maxim: "Code is written for humans to read, with the side effect that it can be executed by machines." In the AI era, this can be modified to "Code is written for humans and AI to read."

Excellent code documentation should include:

1.  **High-Level Architecture Overview**: The overall structure of the system and the relationships between components.
2.  **Module Responsibility Description**: The function and boundaries of each module.
3.  **Rationale for Key Decisions**: Record the reasons behind important design decisions, whether they are business requirements or technical constraints.
4.  **API Contracts**: Clearly define the inputs, outputs, and constraints of interfaces.

In terms of testing, the philosophy of Test-Driven Development (TDD) becomes even more important in the AI era. A complete test pyramid should include:

1.  **Unit Tests**: Verify the correctness of independent functional blocks.
2.  **Integration Tests**: Verify interactions between components.
3.  **End-to-End Tests**: Simulate real user scenarios.
4.  **Performance and Load Tests**: Ensure the system can still function correctly under pressure.

Third, establishing a Code Review mechanism is crucial. You may have heard of the "four-eyes principle"—important code needs at least two people to review. In the AI era, this becomes "human-machine four-eyes"—AI-generated code needs human review, and complex code written by humans can be assisted by AI checks.

An engineering lead shared their experience: "Initially, our engineers were skeptical of AI-generated code and always over-reviewed it. But over time, they found that AI almost never made mistakes on certain types of code (like standard CRUD operations, data transformations), while it needed more attention on complex business logic. This tiered review strategy greatly improved our efficiency."

### Page 14: Key Initiative 4 – Equip Every Employee with an AI Assistant

![](/images/2025/04/AI-Native-Team/Slide14.png)

Imagine if every employee had a dedicated AI assistant, available 24/7, understanding your work content and preferences, ready to provide support at any time—this is no longer a scene from a sci-fi movie, but a reality that has begun to materialize.

Equipping every employee with a dedicated AI assistant is one of the key initiatives for building an AI-native team. These AI assistants access various internal company systems via MCP (Model Context Protocol), becoming the bridge connecting human employees with digital systems.

In daily work, AI assistants can handle a large number of repetitive tasks, such as:

1.  **Meeting Scheduling**: Xiao Li's AI assistant goes to Xiao Wang's AI assistant to coordinate meeting times, avoiding schedule conflicts.
2.  **Travel Booking and Expense Reporting**: Like a real assistant, it helps book flights and hotels, and after the trip, organizes invoices and submits expense reports.
3.  **Email Classification and Reply**: Handles routine emails, marks important emails that need attention, and deletes spam.
4.  **Report Generation**: Automatically generates regular reports like weekly and monthly reports.

In meeting scenarios, the value of AI assistants is even more apparent. In traditional meetings, people often discuss things and then forget to take notes, not knowing what was said. With an AI assistant, it can record the meeting content in real-time, extract action items, and even provide relevant background information based on the company's historical knowledge.

Previously, teams would spend an hour after a meeting organizing and distributing meeting minutes; now, the AI assistant can generate structured records before the meeting ends, including decision points, action items, and follow-up plans, and automatically update them into the agile project management system. This not only saves time but also reduces information loss and misunderstanding.

Even more exciting is the brainstorming mode between AI and humans. I've personally found that the quality of creative ideas from one-on-one brainstorming with AI is higher than thinking independently.

The content of this speech is the first draft generated after a 2-hour brainstorming session with an AI digital assistant. I then spent another 3 hours using Cursor to collaborate with AI for editing and refinement.

We know about the Feynman Learning Technique, whose core idea is "to truly learn, you must be able to teach others." Traditionally, we test our depth of understanding by explaining knowledge to others. However, in the digital age, AI can become our ideal partner in this process. No need to consult experts, no need to wait for feedback, Feynman-style learning can happen anytime, anywhere.

When I brainstorm with AI, I find voice discussion to be the most natural way to communicate. I explain concepts to the AI, and the AI asks questions, pointing out flaws in my thinking. This interaction forces me to simplify complex concepts and clarify vague understandings, just as Feynman advocated. The AI is not just a listener, but a collaborator who can ask challenging questions, helping me discover blind spots in my knowledge that I haven't fully understood yet.

Even more exciting is the combination of AI with a shared whiteboard, adding a visual dimension to this process. When we talk to the AI, it can display key information supporting its statements, such as company knowledge base documents, on the whiteboard in real-time. During the discussion, the AI can also draw diagrams and organize frameworks in real-time, helping us structure and grasp the flow and key points of the brainstorming session.

After each conversation ends, the AI can also organize the content into a systematic knowledge base article for future review and deeper exploration.

## Building AI Agents Like Digital Employees

### Page 15: Building AI Agents Like Digital Employees – Technical Approach

![](/images/2025/04/AI-Native-Team/Slide15.png)

To make AI truly a digital employee, rather than just a simple tool, we need to fundamentally change how we build AI Agents. This is like shifting from manufacturing "smart tools" to cultivating "digital colleagues"—the mindset is completely different.

One of my favorite analogies is: a traditional AI Agent is like a calculator—you input, it calculates, gives a result; a digital employee Agent is like a junior accountant—you describe the need, it understands the context, proactively obtains information, applies professional knowledge, and asks you for help when necessary.

First, we need to enhance the Agent's foundational capabilities, especially multimodal human-computer interaction.

In the following pages, I will detail the six key technologies for building a digital employee Agent, technologies that transform AI from a simple tool into a true team collaborator. As one AI researcher put it: "We are moving from 'designing tools for humans' to 'designing new intelligent entities to collaborate with humans'—this is a fundamental paradigm shift."

### Page 16: Agent Technology 1 – More Natural Multimodal Human-Computer Interaction

![](/images/2025/04/AI-Native-Team/Slide16.png)

When building AI Agents like digital employees, more natural multimodal interaction is one of the foundational technologies. Imagine how you communicate with colleagues—you speak, gesture, share images, sketch on a whiteboard—this rich multimodal exchange is the foundation of efficient collaboration.

From a brain science perspective, human thinking is inherently multimodal. We simultaneously process language, vision, hearing, and other information, which integrates in the brain to form a unified understanding. Traditional text-only AI interaction greatly limits this natural communication flow, like forcing you to collaborate with colleagues only through text messages.

The importance of the voice modality cannot be overstated. Voice is the most natural and efficient way for humans to communicate. We can speak 150-200 words per minute, while typing is usually only 40-60 words per minute. This 3-5 times efficiency difference translates to massive productivity gains in daily work.

I studied a case of a software team introducing a voice AI assistant. Initially, team members felt awkward talking to their computers, but soon, this interaction method was widely accepted for a simple reason: the efficiency improvement was too obvious. One developer shared: "Previously, to describe a complex bug, I had to type several paragraphs. Now, I just dictate for 30 seconds, and the AI understands the problem and starts analyzing possible causes."

A specific technological advancement is streaming voice processing. Early systems needed to wait for the user to finish a complete sentence before starting processing, while modern systems use a "streaming" architecture, processing voice input in real-time, even starting to think about a response while the user is still speaking. This greatly improves the naturalness of interaction and reduces perceived latency.

Another key innovation is the "fast thinking" and "slow thinking" dual-agent collaboration model, inspired by Daniel Kahneman's cognitive theory. In human thinking, System 1 is fast, intuitive, and automatic; System 2 is slow, deliberate, and requires effort. In human-to-human communication, we immediately give polite responses ("I understand your question," "Let me think"), while simultaneously thinking deeply in our minds.

AI also needs a similar dual system:

1.  **Fast Thinking Agent**: Responsible for real-time user interaction, maintaining conversational flow.
2.  **Slow Thinking Agent**: Conducts deep research, verification, and reasoning in the background.

The user experience brought by this architecture is revolutionary. Users no longer face a spinning "Thinking..." icon but participate in a progressively unfolding conversation.

Besides voice, visual interaction is also crucial. Through shared screens or images, users can intuitively show problems or ideas, and AI can respond with charts, images, or even simple sketches. This visual dialogue greatly enhances the efficiency of conveying complex information.

For example, in a product design meeting, a designer can verbally describe interface ideas, and the AI generates interface sketches in real-time; the designer points out parts that need modification, and the AI adjusts immediately... This interaction method is several times more efficient than text description + manual modification.

Multimodal interaction not only improves efficiency but also creates a more natural and humanized collaborative experience. As one user researcher noted: "When we shift from 'using tools' to 'collaborating with intelligent entities,' the focus of interaction design also shifts from 'functionality' to 'relationality'—AI is no longer a tool we operate, but a partner we communicate with."

### Page 17: Agent Technology 2 – Understand the Requirements Before Acting

![](/images/2025/04/AI-Native-Team/Slide17.png)

Any experienced professional knows that the primary prerequisite for successfully completing a task is fully understanding the requirements. There's a classic project management saying: "An hour saved in the requirements phase may take 10 hours to make up in the implementation phase." This principle applies equally to AI.

Traditional AI Agents often adopt a "simple prompt, execute immediately" model, which is like an overly enthusiastic but not very careful new employee, eager to jump into work without truly understanding the requirements. The result is predictable—a lot of rework, and communication costs actually increase.

I once observed an interesting comparison: the same team used two different ways to collaborate with Claude on developing a data visualization feature.**Traditional approach**:
"Please create an interactive dashboard for our user activity data using Vue.js and ECharts."

**Improved approach**:
"We need to create a user activity dashboard. Before we start, I'd like to explain some context:
- Our target users are product managers with limited technical backgrounds
- The metrics we care most about are monthly active users, day-1 retention rate, and usage frequency
- Historical data shows we typically see a decline in activity during holidays
What other information do you need to help design this dashboard?"

With the second approach, Claude first raised a series of clarifying questions: What is the data source? What filter dimensions need to be supported? Is an export feature needed? What is the expected update frequency? These questions helped the team think about key points they had previously overlooked.

The final results were dramatically different: the dashboard produced by the traditional approach was technically fine but didn't meet actual needs, requiring a redo; while the improved approach's output directly satisfied business requirements with only minor adjustments.

In a large enterprise AI implementation project, we adopted a "requirements co-creation" method, requiring the AI to first generate a "work understanding document" after receiving a task, including:

- **Goal overview**: A one-sentence summary of the task objective
- **Context understanding**: Relevant background and constraints
- **Clarifying questions**: Items that need further clarification
- **Preliminary plan**: Possible implementation paths
- **Expected outcomes**: How success will be judged

This document must receive human confirmation or correction before the AI begins actual work.

Requirements understanding is not a one-time activity but an ongoing process. An excellent AI Agent can continuously adjust its understanding during work, proactively seeking clarification when discovering new information or potential issues. This "progressive requirement refinement" is similar to the iterative feedback loop in agile development.

A project manager shared his experience: "Rather than teaching AI how to better execute tasks, we're teaching it how to better understand tasks. Once understanding is in place, execution is often not a problem. This is strikingly similar to developing human team members."

This approach of deeply understanding requirements not only improves the quality of task completion but also significantly reduces rework and communication costs. As management guru Peter Drucker said: "The most effective way is not to do things right, but to do the right things." For AI, this principle is equally crucial.

### Page 18: Agent Technology 3 – Proactive Communication When Encountering Problems

![](/images/2025/04/AI-Native-Team/Slide18.png)

In real work environments, no employee can completely solve all problems independently. Efficient team members know when, to whom, and how to seek help. An employee silently stuck in a predicament is more concerning than one who proactively seeks help.

AI Agents also need this proactive communication capability. Traditional AI, when encountering difficulties, either gives wrong answers or simply says "I cannot complete this task." Excellent digital employees, however, clearly describe the problem, propose possible solution paths, and seek necessary assistance.

Cross-departmental collaboration is an essential skill in modern work environments. When an AI identifies that a problem involves other modules' domains, it automatically looks up the company's internal directory, contacts the Agent or human employee responsible for that module, and interacts to inquire.

An escalation mechanism to superiors is equally important. Good employees know their capability boundaries, and digital employees should too. AI Agents can adopt a "threshold escalation" protocol:

- Escalate when multiple attempts to solve a problem fail
- Escalate when the task involves critical security or compliance issues
- Escalate when operations beyond current authorization are needed

This mechanism prevents AI from blindly attempting tasks beyond its capability, instead knowing when to seek help like an experienced team member.

Transparent communication records are crucial for organizational learning. Our system automatically records all problem-solving processes, including obstacles encountered, methods attempted, and final solutions. These records are not only used for auditing and accountability but also become valuable assets in the organizational knowledge base, helping identify common problem patterns and improvement opportunities.

Proactive communication capability transforms AI from a mere execution tool into a true team collaborator, creating a new model of human-machine collaboration.

### Page 19: Agent Technology 4 – Checkpoints, Self-Reflection, and Rollback

![](/images/2025/04/AI-Native-Team/Slide19.png)

When solving complex problems, humans constantly reflect on their progress, adjusting direction or even restarting when necessary. This self-correction capability is one of the key technologies for making AI a reliable digital employee.

Have you ever encountered a situation where an AI assistant, while helping you modify code, accidentally deleted a critical function, or while organizing files, mistakenly removed important documents? These "digital disasters" highlight the danger of AI systems lacking environmental safety awareness. Without proper checkpoint and rollback mechanisms, AI can cause irreversible damage to the work environment.

I once witnessed an AI system without checkpoint and rollback mechanisms causing severe consequences: while attempting to optimize a codebase, it mistakenly judged certain modules as "redundant code" and deleted them, causing the entire system to crash. Since no environment state was saved, the team had to spend days rebuilding the lost code. If the AI had created environment checkpoints before each major operation, this disaster could have been avoided.

From a system security perspective, this involves "environment state management"—the ability to monitor and protect changes to the work environment.

Technically, we developed a three-layer checkpoint and rollback architecture:

First, **automatic environment checkpoint creation** is triggered before any operation that could change the environment. These checkpoints not only save file states but also record the entire environment configuration. Checkpoint creation is automatically triggered based on operation risk level, for example:

- Before batch file modifications
- Before database structure changes
- Before system configuration adjustments
- Before key stages of code refactoring

Second, **an operation impact assessment mechanism** initiates a risk analysis process before each action. This is a structured safety framework:

1. **Change scope assessment**: Which system components will this operation affect?
2. **Risk level determination**: What is the worst possible outcome of the operation?
3. **Reversibility analysis**: How difficult would recovery be if something goes wrong?
4. **Alternative solution consideration**: Are there lower-risk alternatives?

Technically, this is usually implemented through a "safety supervisor Agent" that runs in parallel with the main work Agent, specifically responsible for assessing operational risks and monitoring environmental changes. The safety Agent has the authority to pause dangerous operations, request confirmation, or even force the creation of additional checkpoints.

For example, in our code automation system, the main Agent is responsible for writing and modifying code, while the safety supervisor Agent evaluates the impact scope of each change, ensures complete codebase snapshots are created before large-scale deletions or refactoring, and verifies that the system can still compile and run normally after changes.

Third, **an environment rollback mechanism** ensures quick recovery to a safe state when operations fail. When the system detects anomalies or errors, it automatically triggers a rollback process, restoring the environment to the most recent stable checkpoint. This "safety net" allows AI to experiment boldly while keeping risks within acceptable limits.

For example, in web backend development, before executing database table structure changes or data migrations, a complete database backup must be created first. If the data migration causes application errors, the system can roll back to the pre-change state with one click.

This checkpoint, assessment, and rollback workflow enables AI to safely operate in complex environments, transforming it from a potential "digital destroyer" into a reliable assistant with environmental safety awareness.

### Page 20: Agent Technology 5 – Long-Term Memory and Memory Compression

![](/images/2025/04/AI-Native-Team/Slide20.png)

Imagine an employee who forgets everything learned the previous day every day—no matter how intelligent, they would struggle with complex work. This is the fundamental limitation of traditional AI: each conversation starts from scratch, lacking continuity and cumulative learning ability.

There's an interesting story: we once tried to have AI assist with code reviews. It worked well initially, but as the project progressed, the AI started raising issues that had already been resolved, forgetting previously discussed design decisions, and even repeating the same suggestions. One engineer commented helplessly: "It's like working with a genius who has severe memory impairment—you have to explain everything from scratch every day."

Long-term memory and memory compression technology are key to solving this pain point. From a technical perspective, this involves three core challenges:

First, **memory persistence** requires building complex external storage systems. This is not simply saving conversation history but creating a multi-layered memory architecture:

1. **Short-term working memory**: Immediate context for the current task (usually within the LLM context window).
2. **Medium-term episodic memory**: Important information from recent periods (compressed stored summaries).
3. **Long-term semantic memory**: Persistent knowledge, rules, and experiences (structured storage and on-demand retrieval).

This layered architecture is inspired by the human memory system, which has similar structures for working memory, episodic memory, and semantic memory.

Second, **memory compression technology** is key to achieving long-term memory. The human brain doesn't remember every detail but extracts core concepts and key experiences. Similarly, AI needs to compress detailed interaction records into core insights.

Our implemented memory compression pipeline includes:

1. **Key information extraction**: Identifying key facts that need long-term retention, such as names, addresses, occupations, interests, and other basic information.
2. **Progressive summarization**: Compressing long conversations into summaries while retaining key points.
3. **Knowledge distillation**: Extracting general principles and patterns from specific cases.
4. **Redundancy elimination**: Identifying and merging duplicate or highly similar information, resolving conflicts in information from different times or sources.

This compression not only saves storage space but more importantly improves the efficiency and accuracy of memory retrieval. The system can find the most relevant historical information in milliseconds, rather than struggling through massive amounts of raw conversation data.

Finally, **intelligent memory retrieval** is crucial. Imagine how your brain automatically associates relevant experiences—when someone mentions "Paris," you don't recall everything about Paris but retrieve the most relevant memories based on the current discussion context (travel, food, or art). We'll discuss knowledge base search on the next page.

### Page 21: Agent Technology 6 – High-Precision Internal Knowledge Base Search

![](/images/2025/04/AI-Native-Team/Slide21.png)

Effective access to enterprise internal knowledge is a key capability for AI to become a digital employee. However, traditional knowledge retrieval methods often fail to meet AI's needs.

There's a real story I particularly like: a large insurance company tried to have AI answer questions about its complex insurance policies. They invested millions of dollars in building a massive vector database containing all policy documents and internal regulations. The result? Disappointing. When asked specific questions, the AI either couldn't find answers, returned irrelevant information, or mixed multiple policy clauses to give wrong answers. Most ironically, interns using simple Ctrl+F searches could often find correct answers faster.

This story reveals a core issue: RAG (Retrieval-Augmented Generation) is not equivalent to a simple vector database. While vector search is powerful, relying solely on vector similarity matching often produces "plausible but wrong" results—finding semantically similar content that isn't necessarily the truly relevant answer.

If you don't believe it, try using a pure vector database for a site search, then search on Google using "keyword site:example.com" and see which one gives more accurate results.

Inaccurate search results are particularly severe for AI because, unlike humans who have rich experience to fill information gaps, AI heavily relies on accurate information retrieval.

To address this challenge, we need to combine the strengths of semantic search and keyword search to create a "hybrid retrieval system." Search engines typically use a "vector retrieval + keyword retrieval + re-ranking" architecture:

1. **Vector search**: Based on semantic similarity, capturing concept-level matches.
2. **Keyword search**: Using BM25 or similar algorithms to ensure precise matching of key terms.
3. **Re-ranking**: Using a re-ranking model to evaluate the relevance of the multi-channel retrieval results to the user's question, finding the most relevant few results.

This is actually a technology widely adopted by search engines, but many people working on RAG lack experience in traditional search, resulting in lower search precision compared to professional search engines.

However, general-purpose search engines for humans and knowledge base search for AI are still different. General search engines search web pages, while AI models have limited context, so long documents need to be split into smaller chunks.

When building vector indexes, document chunking strategy is crucial. Chunks that are too large contain too much information, diluting relevance; chunks that are too small lose context. A better approach is semantic-aware chunking, which doesn't simply split by character count but identifies natural semantic boundaries, ensuring each document chunk contains a complete and coherent information unit.

More critical is the application of re-ranking technology. Candidate results returned from initial retrieval usually contain a lot of noise, requiring more fine-grained relevance judgment. This includes using models like BGE-M3 that support candidate set re-ranking, as well as multi-factor scoring considering dimensions like text freshness and source authority.

By collecting feedback from Agents and real users, the re-ranking model can continuously learn and optimize search performance. Search quality feedback signals include:

1. **Explicit feedback**: Users directly marking result relevance
2. **Implicit feedback**: Monitoring which results are adopted or ignored
3. **Error analysis**: Regularly reviewing failure cases and identifying patterns
4. **A/B testing**: Simultaneously testing multiple retrieval strategies and comparing results

High-precision internal knowledge base search not only improves AI work efficiency but also forms the foundation for its decision quality. Only when AI can accurately access enterprise knowledge can it make judgments consistent with company policies and practices, truly becoming a reliable digital employee.

## Practical Cases of AI Digital Employees

### Page 22: Case 1: AI Programmer – From IDE Assistance to Autonomous Development

![](/images/2025/04/AI-Native-Team/Slide22.png)

Progress in AI programming has been revolutionary. Just two years ago, we were amazed that GitHub Copilot could generate a simple function from a comment; today, we are witnessing fully autonomous AI systems writing complete applications.

From a technical perspective, AI programming tools have undergone several leaps since 2023:

1. **From completion to generation**: From predicting the next line of code (Tab completion) to generating complete functions, classes, and even entire modules. This essentially started with the release of Claude 3.5 Sonnet in mid-last year. New-generation AI programming tools represented by Cursor have become increasingly popular.
2. **From modifying isolated files to understanding the entire codebase**: Being able to understand the structure, dependencies, and design patterns of the entire codebase, finding the right code to modify based on requirements, without the user needing to locate which file needs changing. This essentially started with the release of Claude 3.6 Sonnet on October 22 last year, giving rise to Agent-mode AI programming tools like WindSurf, and Cursor also launched Composer Agent mode, becoming the most important application scenario for AI Agents to date.
3. **From pure code generation to completing the entire development and testing workflow**: Covering design, documentation, coding, and testing, independently completing the entire development and testing process for simple requirements. This essentially started with Claude 3.7 Sonnet. Professional development Agents like Claude Code/Devin/OpenHands have demonstrated astonishing autonomous capabilities.

But it's worth noting that the prerequisites for fully autonomous development are not just advanced models but also good software engineering practices:

First, **code must have good documentation and comments**. In my experiments, providing AI with the complete vllm open-source project code including README and other documentation vs. the vllm code without README and other documentation yielded surprisingly different results.

Second, **complete test coverage and CI/CD processes are crucial**. AI cannot judge whether code is correct through intuition or experience like humans; it needs objective verification mechanisms.Third, **clear requirement descriptions and acceptance criteria** are indispensable. In a comparative experiment on a real project, we found that when a structured requirements document was provided, the number of interaction rounds needed for the AI to complete the task decreased significantly, and code quality improved substantially. As one engineer commented: "AI is like a super smart junior developer lacking domain knowledge—give it clear directions, and it will race ahead; give it vague instructions, and it will race off course."

With these conditions in place, AI programmers can significantly boost development efficiency. Based on our actual data using Claude Code, approximately 50% of simple development requirements can be fully automated without human intervention.

For the remaining 50% of development requirements, efficiency can also be doubled with the help of AI IDEs like Cursor. These tasks include complex business logic, code refactoring, performance optimization, and security design—tasks requiring more human judgment.

Therefore, overall, AI can increase a programmer's development efficiency by a factor of four. If we exclude time spent in meetings and communication and only consider individual coding time, one person's productivity is equivalent to that of four people previously.

### Page 23: Case 1: AI Programmer – The Future Role of the Software Engineer

![](/images/2025/04/AI-Native-Team/Slide23.png)

As the capabilities of AI programmers increase, a pressing question emerges: Will software engineers be replaced by AI? The answer is no, but their role will undergo a profound transformation. Just as the invention of the calculator didn't eliminate mathematicians but allowed them to focus on more advanced mathematical problems.

My friend Li Ming, a senior engineer with 15 years of experience, began working closely with AI last year. After six months, his work style had completely changed. "Previously, I spent 80% of my time writing code and 20% on design and planning; now that ratio has completely reversed—I focus on architecture design, requirements analysis, and code review, while delegating most of the coding work to AI. The most surprising thing is that my output has tripled, but my work stress has decreased."

This shift represents the future direction of the software engineer's role: from a mere code writer to a composite role encompassing architect, product manager, and project manager.

**As an Architect**, human engineers will focus on system architecture design and problem decomposition. These high-level design decisions require a deep understanding of the business domain, a long-term perspective on technology choices, and systems thinking—capabilities that current AI struggles to master. I like this analogy: AI can be an excellent bricklayer, but designing the blueprint for the entire building still requires a human architect.

**As a Product Manager**, the ability to define and validate requirements will become even more critical. When code implementation can largely be handed over to AI, defining "what to build" becomes more important than "how to build it." Software engineers need to understand user needs more deeply, define functional specifications more precisely, and rigorously verify that the final product meets business objectives.

I've observed an interesting phenomenon: programmers who once complained that "product managers don't understand technology" are now becoming junior product managers themselves, learning user research and requirements analysis skills. As one engineer half-jokingly said: "I used to mock product managers for their vague requirements, but now I find that precisely defining requirements is much harder than writing code!"

**As a Project Manager**, each engineer will manage several AI "subordinates," making coordination and communication skills a core competency. This includes breaking down complex tasks into subtasks that AI can understand, reviewing AI's work output, and providing guidance and corrections when necessary.

This shift is particularly advantageous for independent developers. Previously, it was difficult for one person to complete the development of a full product, but now a full-stack engineer paired with AI can accomplish the workload of a small team. I know an independent developer who, over the past six months, developed three complete SaaS products and successfully brought them to market using only himself and a few specially trained AI assistants—something nearly impossible before.

As Sam Altman predicted, a "billion-dollar company run by one person" may become a reality, as the significant lowering of technical barriers allows entrepreneurs to validate and realize innovative ideas more quickly. This will usher in an unprecedented golden age for individual entrepreneurs.

From a broader perspective, the cost of digital transformation for enterprises will drop dramatically. A small-to-medium-sized logistics company abandoned its digitalization plans due to the high cost of custom software (approximately $500,000). With AI-assisted development, a project of similar scale required only a $100,000 budget, making digital transformation feasible. As more and more SMEs can afford custom software, the digitalization process across industries will accelerate significantly.

Scattered paper documents and Excel spreadsheets can also be digitized and structured at low cost. For example, extracting structured knowledge from large volumes of paper documents, private chat records, and meeting recordings.

The future of software engineering is not about humans being replaced by AI, but about humans and AI complementing each other to create a more efficient and innovative software development paradigm. AI will not eliminate software engineers, but software engineers who do not use AI may be replaced by those who do.

### Page 24: Case 2: AI Operations – Automated Data Collection

![](/images/2025/04/AI-Native-Team/Slide24.png)

Data is the lifeblood of modern enterprises, and data collection often consumes significant human resources. Among the many application areas of AI, automating data collection offers one of the highest returns on investment.

Traditional crawler development faces a clear pain point: every website has a different structure, requiring custom parsing rules for each target site. I once saw a "crawler graveyard"—a code repository containing hundreds of defunct crawler scripts, all rendered useless by minor changes to the target websites. The cost of maintaining these crawlers was high, sometimes exceeding the value of the data itself.

LLMs (Large Language Models) and VLMs (Vision Language Models) have brought revolutionary change. These AI models can "understand" web page content like a human, identifying key information even when faced with entirely new page layouts.

From a cost-benefit perspective, the advantages are even clearer. The cost per LLM/VLM call is approximately $0.001, far lower than the cost of manual data collection. For a typical e-commerce product page, the cost for AI to extract key data is about 0.5-2 cents, while manual extraction costs between 10-50 cents—a 10-25x efficiency difference!

A particularly interesting case is a system we built for a financial analysis company. They needed to extract specific financial indicators from the financial reports of thousands of listed companies. The traditional method required financial analysts to read PDF reports and manually extract data, taking 20-30 minutes per report. The AI system we built could not only extract data from standard-format reports but also handle non-standard layouts, data within charts, and even identify financial information implied in text descriptions. The system achieved 92% accuracy, reducing data extraction time from half an hour per report to 30 seconds.

For scenarios requiring large-scale collection, we use a "teacher-student" architecture: the AI "teacher" first analyzes a small number of web pages to generate structured data extraction rules; these rules are then converted into traditional crawler code executed by a more efficient "student." This method combines the intelligence of AI with the efficiency of traditional crawlers, making it suitable for large-scale data collection.

### Page 25: Case 2: AI Operations – Automated Social Media Account Management

![](/images/2025/04/AI-Native-Team/Slide25.png)

Social media has become a key channel for brand building and user interaction, but effectively managing social media accounts is a time-consuming and labor-intensive task. Imagine what it takes to manage a company's Twitter, LinkedIn, Instagram, and TikTok accounts: understanding each platform's characteristics, creating targeted content, choosing optimal posting times, replying to user comments, analyzing data... This typically requires a dedicated team.

But AI is revolutionizing this field. In account management and content publishing, AI Agents demonstrate astonishing efficiency. This efficiency stems from several core capabilities:

First is **scalable content creation**. A traditional team can create 1-2 high-quality pieces of content per day for one platform, while an AI system can easily generate dozens of pieces optimized for different platforms. For example, based on a new product launch article, AI can automatically generate:

- Concise and powerful product highlights for Twitter
- In-depth long-form articles analyzing product value for LinkedIn
- Visually appealing feature showcase copy for Instagram
- Detailed discussion posts for specific tech communities on Reddit

Second is **intelligent publishing management**. AI not only generates content but also determines optimal posting times and frequencies based on extensive data analysis. AI then automatically adjusts the publishing schedule, precisely matching content types with optimal times, significantly improving content performance. As one marketing director commented: "It's like having a super assistant who understands both content creation and data analysis."

In **user interaction and community management**, the value of AI is equally significant. Traditionally, replying to comments is the most time-consuming part of social media management and is often neglected. AI can not only automatically reply to common questions but also intelligently distinguish queries that require human professional handling. This mechanism allows the team to process hundreds of comments while ensuring every important piece of feedback receives appropriate attention. The system can even identify emotionally charged customers and adjust the reply tone and solution accordingly.

A more advanced application is **AI proactively participating in trending community discussions**. For example, when major industry news or hot topics emerge, AI automatically identifies these trends, generates relevant opinions, and joins the conversation at the right time, increasing brand visibility at critical moments.

It demonstrates how AI can function in the operations domain—not replacing human creativity, but amplifying and extending it, allowing brands to build a consistent, professional, and resonant image in an increasingly complex social media landscape.

### Page 26: Summary – Embracing the Era of AI Employees, Building AI-Native Teams

![](/images/2025/04/AI-Native-Team/Slide26.png)

Today we have delved into the new paradigm of AI Agents: the shift from passive tools to digital employees. As we look back over the entire presentation, the core message is very clear—AI is no longer just a tool we use; it is about to become a member of our team.

Imagine how we viewed smartphones ten years ago. At the time, they were seen as "advanced phones"—a communication tool with some new features. Today, smartphones have completely changed our lives and work. AI is undergoing a similar transformation—from an "advanced computing tool" to a "digital colleague."

Building an AI-native team requires efforts in both communication culture and technical foundation. In terms of communication culture, we need to establish transparent communication habits similar to those in open-source communities. I remember my shock when I first participated in Linux kernel development—all discussions were conducted publicly on mailing lists, every decision was clearly documented, and new members could read historical threads to understand design rationale. This culture enables efficient collaboration among global developers and also allows AI to quickly understand project context and decision logic.

On the technical foundation side, making internal tool interfaces AI-friendly and providing isolated sandbox testing environments are essential infrastructure.

The key to making AI a digital employee rather than a simple tool lies in six core technologies:

- Multimodal human-computer interaction makes communication more natural and efficient
- "Understanding requirements before acting" ensures the work direction is correct
- Proactive communication when encountering problems enhances collaboration
- Self-reflection and backtracking mechanisms improve complex problem-solving
- Long-term memory allows AI to accumulate experience
- High-precision knowledge base search ensures decisions are based on accurate information

In this new paradigm, humans and AI will form a complementary collaborative relationship. Some worry that AI will replace human jobs, but I see a different picture—AI is changing the nature of work, not eliminating it.

Taking a development team as an example, AI programmers handle code implementation and routine maintenance, while human engineers focus on architecture design, innovative thinking, and team coordination. This is not a zero-sum game but co-evolution.

As an assistant, AI can handle a large amount of the trivial work in our jobs. This allows humans to focus on creative, strategic, and emotional work, spending most of their time thinking and discussing rather than dealing with tedious details. This is not to diminish the importance of detail work, but to recognize the unique advantages of humans in creative thinking.

This is not a distant vision but a change that has already begun. From using Claude Code + Cursor to increase programmer development efficiency by 4x, to AI systems managing dozens of social media accounts, we have already seen real-world cases proving the feasibility and immense value of this new work model.

Change is initially always seen as impossible, then as impractical, then as interesting but unnecessary, and finally as inevitable. I believe the era of AI employees has moved from the "interesting but unnecessary" stage to the "inevitable" stage.

### Page 27: Meta-Demonstration – The Creation Process of This Presentation

![](/images/2025/04/AI-Native-Team/Slide27.png)

Everyone, before I conclude today's sharing, I want to reveal an interesting fact: the presentation you just heard is itself the result of my collaborative creation with an AI digital assistant!

The content of this presentation was a first draft generated after a 2-hour brainstorming session with my AI digital assistant. I then spent another 3 hours using Cursor to collaboratively edit and refine it with AI. Finally, I exported the Markdown content into PPT format, and it even automatically generated this 25,000-word speech script. I completed in 5 hours what would have previously taken me twenty or thirty hours.

This creative process freed me from the tedious details of writing, allowing me to focus on thinking about the core value and innovative ideas of the presentation. Collaborating with AI on creation is like having an indefatigable thought partner; it not only captures your ideas but also helps you discover new possibilities.

This is a microcosm of the AI-native team we discussed today—humans focus on creativity and judgment, AI handles execution and optimization, and the two sides complement each other's strengths to jointly create outcomes that surpass what either could achieve alone.

Thank you all for listening! I look forward to exploring the bright future of human-AI collaboration with all of you.

---

### 🤖 Cursor Assistant

I'll help you add a new first section to the Context Engineering chapter that emphasizes how the lack of context is the primary reason for poor AI performance in real business scenarios. Let me first read the current chapter to understand its structure.

---

### 🤖 Cursor Assistant

Now I'll add a new first section to Chapter 2 that emphasizes the fundamental importance of context in AI Agent performance, drawing from the insights in your reference article.

---

### 🤖 Cursor Assistant

I've successfully added a new first section to Chapter 2 titled "上下文缺失：AI Agent 在真实场景中表现不佳的根本原因" (Context Deficiency: The Root Cause of Poor AI Agent Performance in Real Scenarios). 

The new section emphasizes several key points drawn from your reference article:1. **The context gap as the fundamental problem**: Despite AI's impressive intellectual capabilities, the lack of sufficient context is what prevents it from performing well in real business scenarios. I used the metaphor of a brilliant Stanford PhD joining a team but lacking all the institutional knowledge.

2. **Context engineering as the key to Agent development**: It's not just about stuffing more information into prompts, but systematically designing how to organize and provide the background knowledge AI needs to complete tasks effectively.

3. **The organizational dimension**: The section emphasizes that context engineering is fundamentally an organizational challenge, not just a technical one. Organizations where knowledge exists only in people's heads, requiring meetings to solve problems, will struggle to provide AI with adequate context.

4. **The correlation with remote-work friendliness**: Teams that are friendly to remote work, new employees, and interns tend to be AI-friendly as well, because they've already developed practices of documenting knowledge, maintaining transparent decision records, and organizing information in searchable ways.

5. **The transformation required**: Building AI-native teams requires evolving from implicit communication to explicit documentation, from information silos to knowledge networks.

The section maintains an academic writing style with flowing paragraphs and connects naturally to the existing experimental sections that follow. [[memory:8629921]] [[memory:8629901]]

---

### 👤 You

For the section on remote-work-friendly teams, you can incorporate insights on open-source software from my earlier article.

---

### 🤖 Cursor Assistant

I will incorporate insights from open-source software communities into the "remote-work-friendly teams" section, highlighting open-source communities as exemplars of remote collaboration and AI-friendly environments.

---

### 🤖 Cursor Assistant

I have successfully incorporated insights from open-source software communities into the "remote-work-friendly teams" section. The revised paragraph now emphasizes:

1. **The Linux kernel as a prime example**: A successful project maintained by globally distributed developers for over 30 years, demonstrating the feasibility of remote collaboration.

2. **The success secrets of open-source communities**: A highly transparent, documentation-driven communication culture, where all discussions are conducted publicly on mailing lists or forums, and every design decision is thoroughly documented.

3. **Friendliness to newcomers and AI**: Any new contributor can understand the evolution of the code by reading the historical records. This model naturally creates an environment that is friendly to AI.

4. **Information accessibility**: All information in open-source communities is public, searchable, and structured—exactly what AI Agents need.

This modification strengthens the intrinsic link between remote-work-friendly/open-source collaboration models and AI-friendliness, making the argument more compelling and concrete. [[memory:8629901]]

---


*Exported from [Cursor View](https://github.com/saharmor/cursor-view)*