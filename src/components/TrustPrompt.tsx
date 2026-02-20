import React, { useState } from 'react';
import { Box, Text, useInput, useApp } from 'ink';
import { trustWorkspace } from '../lib/trust.js';

const LOGO = [
  ' ██████╗ ██╗    ██╗ █████╗ ██████╗ ███╗   ███╗',
  '██╔════╝ ██║    ██║██╔══██╗██╔══██╗████╗ ████║',
  '╚█████╗  ██║ █╗ ██║███████║██████╔╝██╔████╔██║',
  ' ╚════██╗██║███╗██║██╔══██║██╔══██╗██║╚██╔╝██║',
  ' ██████╔╝╚███╔███╔╝██║  ██║██║  ██║██║ ╚═╝ ██║',
  ' ╚═════╝  ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝',
];
const LOGO_COLORS = ['#FFEE00', '#FFD700', '#FFC200', '#FF9F00', '#FF7F00', '#FF5F00'];

interface TrustPromptProps {
  workspace: string;
  mode: string;
  onTrusted: () => void;
}

export function TrustPrompt({ workspace, mode, onTrusted }: TrustPromptProps) {
  const { exit } = useApp();
  const [declined, setDeclined] = useState(false);

  useInput((input, key) => {
    if (declined) return;

    if (input === 'y' || input === 'Y' || key.return) {
      trustWorkspace(workspace);
      onTrusted();
    } else if (input === 'n' || input === 'N' || key.escape) {
      setDeclined(true);
      setTimeout(() => exit(), 50);
    }
  });

  if (declined) {
    return (
      <Box paddingX={2} paddingY={1}>
        <Text dimColor>Trust declined. Exiting.</Text>
      </Box>
    );
  }

  return (
    <Box flexDirection="column">
      {/* Logo */}
      <Box flexDirection="column" marginTop={1} marginLeft={1}>
        {LOGO.map((line, i) => (
          <Text key={i} bold color={LOGO_COLORS[i]}>{line}</Text>
        ))}
      </Box>

      <Box
        flexDirection="column"
        borderStyle="round"
        borderColor="yellow"
        paddingX={2}
        paddingY={1}
        marginTop={1}
        marginBottom={1}
      >
      <Text bold color="yellow">Trust Required</Text>
      <Text> </Text>
      <Text><Text dimColor>  Workspace:  </Text><Text bold>{workspace}</Text></Text>
      <Text><Text dimColor>  Mode:       </Text><Text bold color="red">{mode}</Text></Text>
      <Text> </Text>
      <Text dimColor>
        Agent Swarm will grant agents elevated permissions in this{'\n'}
        directory. Each agent's individual trust check is bypassed.
      </Text>
      <Text> </Text>
      <Text>
        <Text bold color="yellow">Trust this workspace?</Text>
        <Text dimColor>  Y / Enter to trust  ·  N / Esc to cancel</Text>
      </Text>
    </Box>
    </Box>
  );
}
