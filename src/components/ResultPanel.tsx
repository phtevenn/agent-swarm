import React from 'react';
import { Box, Text } from 'ink';
import type { WorkerState } from '../types.js';

function tailLines(text: string, n: number): string {
  const lines = text.split('\n');
  return lines.length > n ? lines.slice(-n).join('\n') : text;
}

interface ResultPanelProps {
  worker: WorkerState;
  verbose?: boolean;
}

export function ResultPanel({ worker, verbose }: ResultPanelProps) {
  const success = worker.status === 'done';
  const borderColor = success ? 'green' : 'red';
  const icon = success ? '✓' : '✗';
  const elapsed = worker.endedAt ? ((worker.endedAt - worker.startedAt) / 1000).toFixed(0) : '?';

  const content = success
    ? (verbose ? worker.output : tailLines(worker.output ?? '', 15))
    : worker.error;  // Always show full error text

  return (
    <Box flexDirection="column" borderStyle="round" borderColor={borderColor} paddingX={1} marginX={1} marginBottom={1}>
      <Box>
        <Text bold color={borderColor}>{icon} {worker.name}</Text>
        <Text dimColor>  {elapsed}s</Text>
      </Box>
      {content ? <Text>{content}</Text> : null}
    </Box>
  );
}
