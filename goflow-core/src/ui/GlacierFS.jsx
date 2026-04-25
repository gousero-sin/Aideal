import React, { useState } from 'react';
import { Folder, FileText, HardDrive } from 'lucide-react';

const mockFileSystem = {
    name: 'Root',
    type: 'folder',
    children: [
        {
            name: 'System',
            type: 'folder',
            children: [
                { name: 'Core.sys', type: 'file' },
                { name: 'Config.ini', type: 'file' },
            ]
        },
        {
            name: 'Users',
            type: 'folder',
            children: [
                {
                    name: 'Guest',
                    type: 'folder',
                    children: [
                        { name: 'Documents', type: 'folder', children: [] },
                        { name: 'Downloads', type: 'folder', children: [] },
                        { name: 'Notes.txt', type: 'file' },
                    ]
                }
            ]
        },
        { name: 'Readme.md', type: 'file' }
    ]
};

const GlacierFS = () => {
    const [currentPath, setCurrentPath] = useState([mockFileSystem]);

    const currentFolder = currentPath[currentPath.length - 1];

    const handleNavigate = (item) => {
        if (item.type === 'folder') {
            setCurrentPath([...currentPath, item]);
        }
    };

    const handleUp = () => {
        if (currentPath.length > 1) {
            setCurrentPath(currentPath.slice(0, -1));
        }
    };

    return (
        <div className="flex h-full bg-white/5 text-xs text-white">
            {/* Sidebar */}
            <div className="w-1/3 border-r border-white/10 p-2 space-y-2">
                <div className="font-semibold opacity-50 mb-2">DRIVES</div>
                <div className="flex items-center gap-2 px-2 py-1 bg-blue-500/20 rounded cursor-pointer">
                    <HardDrive size={14} /> Local Disk (C:)
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex flex-col">
                {/* Breadcrumbs */}
                <div className="p-2 border-b border-white/10 flex items-center gap-2">
                    <button onClick={handleUp} disabled={currentPath.length <= 1} className="px-2 py-0.5 bg-white/10 rounded disabled:opacity-30">
                        Up
                    </button>
                    <span className="opacity-70">
                        {currentPath.map(f => f.name).join(' / ')}
                    </span>
                </div>

                {/* File List */}
                <div className="p-2 grid grid-cols-4 content-start gap-2 overflow-auto">
                    {currentFolder.children?.map((item, i) => (
                        <div
                            key={i}
                            onDoubleClick={() => handleNavigate(item)}
                            className="flex flex-col items-center gap-1 p-2 hover:bg-white/10 rounded cursor-pointer transition-colors"
                        >
                            <div className="w-10 h-10 bg-white/10 rounded flex items-center justify-center">
                                {item.type === 'folder' ? <Folder size={20} className="text-yellow-400" /> : <FileText size={20} className="text-blue-300" />}
                            </div>
                            <span className="text-center truncate w-full">{item.name}</span>
                        </div>
                    ))}
                    {currentFolder.children && currentFolder.children.length === 0 && (
                        <div className="col-span-4 text-center opacity-30 py-4">Empty Folder</div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default GlacierFS;
