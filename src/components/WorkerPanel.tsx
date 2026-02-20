import React, { useState, useEffect } from 'react';
import { Box, Text } from 'ink';
import { WorkerRow } from './WorkerRow.js';
import type { WorkerState } from '../types.js';

const SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

export function WorkerPanel({ workers }: { workers: WorkerState[] }) {
  const [frame, setFrame] = useState(0);

  // One shared timer for all spinners — prevents N independent re-render sources.
  const hasRunning = workers.some(w => w.status === 'running');
  useEffect(() => {
    if (!hasRunning) return;
    const id = setInterval(() => setFrame(f => (f + 1) % SPINNER_FRAMES.length), 100);
    return () => clearInterval(id);
  }, [hasRunning]);

  const spinnerChar = SPINNER_FRAMES[frame];

  return (
    <Box flexDirection="column" borderStyle="single" borderColor="blue" paddingX={1} marginX={1} marginBottom={1}>
      <Text bold color="blue">Workers</Text>
      {workers.map(w => <WorkerRow key={w.name} worker={w} spinnerChar={spinnerChar} />)}
    </Box>
  );
}
