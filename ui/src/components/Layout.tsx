import { useEffect, useState } from "react";
import Chat from "./Chat";
import Logs from "./Logs";
import type { Message } from "../types";

const Layout = () => {
    const [logs, setLogs] = useState<string[]>([]);
    const [messages, setMessages] = useState<Message[]>([]);
    const [socket, setSocket] = useState<WebSocket | null>(null);

    useEffect(() => {
        const ws = new WebSocket("ws://localhost:8000/ws");

        ws.onopen = () => {
            setLogs((prev) => [...prev, "Connected"]);
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);

            if (msg.type === "log") {
                setLogs((prev) => [...prev, msg.data]);
            }

            if (msg.type === "chat") {
                setMessages((prev) => [
                    ...prev,
                    {
                        id: Date.now(),
                        text: msg.data,
                        sender: "system",
                    },
                ]);
            }
        };

        ws.onclose = () => {
            setLogs((prev) => [...prev, "Disconnected"]);
        };

        setSocket(ws);

        return () => ws.close();
    }, []);

    return (
        <div className="flex h-screen">
            {/* Chat */}
            <div className="w-1/2 border-r">
                <Chat
                    socket={socket}
                    messages={messages}
                    setMessages={setMessages}
                />
            </div>

            {/* Logs */}
            <div className="w-1/2">
                <Logs logs={logs} />
            </div>
        </div>
    );
};

export default Layout;