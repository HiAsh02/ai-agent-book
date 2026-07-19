"""
Simulated user: Automatically answer the Agent's questions during the requirements clarification phase, enabling unattended execution of all three phases.

In a real product, ask_clarifying_question would send questions to a human; here, a set of preset answers is used,
matching the Agent's questions by keyword scoring (the one with the most keyword hits wins).
Additionally, a deduplication mechanism is built in: if the same question is repeatedly asked, it explicitly tells the Agent
"Already answered, no further requirements, please start implementation" to avoid an infinite loop in the clarification phase.
"""

from typing import Dict, List, Tuple


class SimulatedUser:
    def __init__(self) -> None:
        # (keyword list, preset answer). The more keywords hit, the higher the priority.
        self.playbook: List[Tuple[List[str], str]] = [
            (["Type", "Format", "Extension", "Category", "type", "kind"],
             "Classify by file type: images (jpg/png/gif), documents (pdf/doc/txt),"
             "audio (mp3/wav), video (mp4/mov), archives (zip/rar), and others go to Others."),
            (["Recursive", "Subdirectory", "Subfolder", "recursive", "subfolder"],
             "No recursion needed, only organize the current level of the download folder, ignoring existing subfolders inside."),
            (["Original filename", "Rename", "Keep name", "Same name", "Conflict", "Duplicate", "Overwrite", "rename", "conflict"],
             "Keep the original filename; if a file with the same name already exists, append _1, _2 to avoid overwriting."),
            (["Move", "Copy", "Cut", "move", "copy"],
             "Use move instead of copy; after organizing, the original location will no longer retain these files."),
            (["Destination", "Target", "Save to", "Store to", "Path", "Location", "which folder", "destination", "location", "path"],
             "No need to specify a target directory separately: create subfolders by category inside the download folder"
             "(Images/Documents/Audio/Video/Archives/Others), and move files into the corresponding subfolder."
             "The path of the download folder itself is passed via a command-line argument; if not provided, default to ~/Downloads."),
            (["Date", "Time", "date", "time"],
             "No need to sort by date, only by type."),
            (["Confirm", "Start", "Also", "Other", "Else", "Additional", "proceed", "anything else"],
             "No other requirements, that's all. You can start implementing."),
        ]
        self.default_answer = "Just handle it with common sense, no need to be too complex; keep the script simple and readable."
        self.qa_log: List[Tuple[str, str]] = []
        self._asked_count: Dict[str, int] = {}

    def _match(self, q: str) -> str:
        best_reply, best_score = self.default_answer, 0
        for keywords, reply in self.playbook:
            score = sum(1 for kw in keywords if kw.lower() in q)
            if score > best_score:
                best_reply, best_score = reply, score
        return best_reply

    def answer(self, question: str) -> str:
        norm = "".join(question.lower().split())
        self._asked_count[norm] = self._asked_count.get(norm, 0) + 1

        #  Prevent repetition: if the same question is asked a second time, urge the Agent to end clarification and proceed to implementation
        if self._asked_count[norm] >= 2:
            reply = (
                "I have already answered this question; there are no other requirements."
                "The requirements are clear enough; please directly call complete_requirements_analysis to enter the implementation phase."
            )
        else:
            reply = self._match(question)

        self.qa_log.append((question, reply))
        return reply
