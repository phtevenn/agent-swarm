import React from 'react';
import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';
import type { WorkerState } from '../types.js';

export function WorkerRow({ worker }: { worker: WorkerState }) {
  const elapsed = ((Date.now() - worker.startedAt) / 1000).toFixed(0);
  const icon = worker.status === 'running'
    ? <Text color="cyan"><Spinner type="dots" /></Text>
    : worker.status === 'done'
      ? <Text color="green">✓</Text>
      : <Text color="red">✗</Text>;

  return (
    <Box>
      {icon}
      <Text> </Text>
      <Text bold color="blue">{worker.name.padEnd(12)}</Text>
      <Text dimColor>{(worker.lastLine ?? '').slice(0, 60)}</Text>
      <Text dimColor>  {elapsed}s</Text>
    </Box>
  );
}
