import _ from 'lodash';
import { useEffect, useState } from 'react';

import { LinkTo } from '@/components/LinkTo';
import { cn } from '@/lib/utils';
import { deepJsonParse } from '@/utils/jsonUtils';

function preWrap(message, maxCharacters = 80) {
    if (!maxCharacters) {
        return message;
    }
    const lines = message.split('\n');
    let newLines = [];
    for (let i = 0; i < lines.length; i++) {
        let line = lines[i];
        for (let l = 0; l < line.length; l += maxCharacters) {
            let newLine = line.slice(l, l + maxCharacters);
            newLines.push(newLine);
        }
    }
    return newLines.join('\n');
}

function JSONExpandableMessage({ message, isExpanded: initIsExpanded, className, maxCharacters = null }) {
    const [isExpanded, setIsExpanded] = useState(initIsExpanded);

    useEffect(() => {
        setIsExpanded(initIsExpanded);
    }, [initIsExpanded]);

    let messageJson = deepJsonParse(message);
    if (_.isString(messageJson)) {
        return <div className="font-mono">{message}</div>;
    }

    const json = JSON.stringify(messageJson, null, 2);
    let displayJson = preWrap(json, maxCharacters);
    while (displayJson.includes('\\n')) {
        displayJson = displayJson.replace(/\\n/g, '\n');
    }
    const displayMessage = preWrap(message, maxCharacters);

    return !isExpanded ? (
        <div className="font-mono">
            <div
                className={cn(className, {
                    'whitespace-pre': maxCharacters,
                    'break-all': !maxCharacters,
                })}
            >
                {displayMessage}
            </div>
            <div className="flex justify-end gap-2">
                <span
                    className="cursor-pointer text-blue-500 hover:underline"
                    onClick={() => {
                        navigator.clipboard.writeText(json);
                    }}
                >
                    [Copy]
                </span>
                <LinkTo onClick={() => setIsExpanded(true)}>[Format JSON]</LinkTo>
            </div>
        </div>
    ) : (
        <div className="font-mono">
            <div
                className={cn(className, {
                    'whitespace-pre': maxCharacters,
                    'break-all whitespace-pre-wrap': !maxCharacters,
                })}
            >
                {displayJson}
            </div>
            <div className="text-right">
                <LinkTo onClick={() => setIsExpanded(false)}>[Show original]</LinkTo>
            </div>
        </div>
    );
}

export default JSONExpandableMessage;
