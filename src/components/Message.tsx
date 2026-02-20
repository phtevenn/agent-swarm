import React from 'react';
import { Box, Text } from 'ink';
import type { ChatMessage } from '../types.js';

export function Message({ role, text }: ChatMessage) {
  if (role === 'user') {
    return (
      <Box flexDirection="column" marginBottom={1}>
        <Text bold color="green">{'> '}{text}</Text>
      </Box>
    );
  }
  if (role === 'system') {
    return (
      <Box marginBottom={1} paddingX={2}>
        <Text dimColor italic>{text}</Text>
      </Box>
    );
  }
  // assistant
  return (
    <Box flexDirection="column" marginBottom={1} paddingX={2}>
      <Text dimColor>claude-code</Text>
      <Text>{text}</Text>
    </Box>
  );
}
