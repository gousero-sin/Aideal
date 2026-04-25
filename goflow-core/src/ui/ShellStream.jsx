import React, { useState, useEffect, useRef } from 'react';

const ShellStream = () => {
    const [history, setHistory] = useState([
        { type: 'output', content: 'GoFlowOS Shell v1.0' },
        { type: 'output', content: 'Type "help" for available commands.' },
    ]);
    const [input, setInput] = useState('');
    const bottomRef = useRef(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [history]);

    const handleCommand = (cmd) => {
        const args = cmd.trim().split(' ');
        const command = args[0].toLowerCase();

        let output = '';

        switch (command) {
            case 'help':
                output = 'Available commands: help, clear, echo, date, whoami, uname';
                break;
            case 'clear':
                setHistory([]);
                return;
            case 'echo':
                output = args.slice(1).join(' ');
                break;
            case 'date':
                output = new Date().toString();
                break;
            case 'whoami':
                output = 'user@goflow';
                break;
            case 'uname':
                output = 'GoFlowOS v1.0 (HydroKernel)';
                break;
            default:
                output = `Command not found: ${command}`;
        }

        setHistory(prev => [...prev, { type: 'input', content: cmd }, { type: 'output', content: output }]);
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            handleCommand(input);
            setInput('');
        }
    };

    return (
        <div className="h-full bg-black/80 font-mono text-xs p-2 text-green-400 overflow-auto">
            {history.map((line, i) => (
                <div key={i} className={line.type === 'input' ? 'text-white' : 'text-green-300'}>
                    {line.type === 'input' ? '> ' : ''}{line.content}
                </div>
            ))}
            <div className="flex">
                <span className="text-white mr-2">{'>'}</span>
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    className="bg-transparent border-none outline-none flex-1 text-white"
                    autoFocus
                />
            </div>
            <div ref={bottomRef} />
        </div>
    );
};

export default ShellStream;
