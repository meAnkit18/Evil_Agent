export interface Message {
    id: number;
    text: string;
    sender: "user" | "system";
}

export interface Log {
    id: number;
    text: string;
}