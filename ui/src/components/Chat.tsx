import { useState } from "react";
import type { Message } from "../types";

interface Props {
    socket: WebSocket | null;
    messages: Message[];
    setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
}

const Chat = ({ socket, messages, setMessages }: Props) => {
    const [input, setInput] = useState("");

    const handleSend = () => {
        if (!input.trim() || !socket) return;

        // send to backend
        socket.send(
            JSON.stringify({
                type: "chat",
                data: input,
            })
        );

        // update UI
        setMessages((prev) => [
            ...prev,
            {
                id: Date.now(),
                text: input,
                sender: "user",
            },
        ]);

        setInput("");
    };

    return (
        <div className="flex flex-col h-full p-3">

            {/* Messages */}
            <div className="flex-1 overflow-y-auto space-y-2">
                {messages.map((msg) => (
                    <div key={msg.id} className="text-sm">
                        <span className="font-semibold">{msg.sender}:</span> {msg.text}
                    </div>
                ))}
            </div>

            {/* Input */}
            <div className="flex gap-2 mt-2">
                <input
                    className="flex-1 border px-2 py-1 rounded"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSend()}
                />
                <button
                    className="border px-3 py-1 rounded"
                    onClick={handleSend}
                >
                    Send
                </button>
            </div>
        </div>
    );
};

export default Chat;