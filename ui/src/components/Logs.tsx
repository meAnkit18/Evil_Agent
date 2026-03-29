interface Props {
    logs: string[];
}

const Logs = ({ logs }: Props) => {
    return (
        <div className="h-full p-3 overflow-y-auto">
            <h2 className="font-bold mb-2">Logs</h2>

            <div className="space-y-1 text-sm">
                {logs.map((log, i) => (
                    <div key={i}>{log}</div>
                ))}
            </div>
        </div>
    );
};

export default Logs;