import React from 'react';
import { Box, Text } from 'ink';
import { WorkerRow } from './WorkerRow.js';
import type { WorkerState } from '../types.js';

export function WorkerPanel({ workers }: { workers: WorkerState[] }) {
  return (
    <Box flexDirection="column" borderStyle="single" borderColor="blue" paddingX={1} marginX={1} marginBottom={1}>
      <Text bold color="blue">Workers</Text>
      {workers.map(w => <WorkerRow key={w.name} worker={w} />)}
    </Box>
  );
}
