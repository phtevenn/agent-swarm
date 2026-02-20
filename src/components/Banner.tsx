import React from 'react';
import { Box, Text } from 'ink';

// ANSI Shadow style — "SWARM"
const LOGO = [
  ' ██████╗ ██╗    ██╗ █████╗ ██████╗ ███╗   ███╗',
  '██╔════╝ ██║    ██║██╔══██╗██╔══██╗████╗ ████║',
  '╚█████╗  ██║ █╗ ██║███████║██████╔╝██╔████╔██║',
  ' ╚════██╗██║███╗██║██╔══██║██╔══██╗██║╚██╔╝██║',
  ' ██████╔╝╚███╔███╔╝██║  ██║██║  ██║██║ ╚═╝ ██║',
  ' ╚═════╝  ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝',
];

// Yellow → orange gradient top to bottom
const LOGO_COLORS = ['#FFEE00', '#FFD700', '#FFC200', '#FF9F00', '#FF7F00', '#FF5F00'];

interface BannerProps {
  workspace: string;
  configSource: string;
  leadName: string;
  workerNames: string[];
  approvalMode: string;
}

export function Banner({ workspace, configSource, leadName, workerNames, approvalMode }: BannerProps) {
  const workersStr = workerNames.length > 0 ? workerNames.join(', ') : '(none)';
  return (
    <Box flexDirection="column" marginBottom={1}>
      {/* ASCII art logo */}
      <Box flexDirection="column" marginTop={1} marginLeft={1}>
        {LOGO.map((line, i) => (
          <Text key={i} bold color={LOGO_COLORS[i]}>{line}</Text>
        ))}
      </Box>

      {/* Tagline */}
      <Box marginLeft={2} marginTop={1}>
        <Text dimColor>orchestrate multiple coding agents</Text>
        <Text dimColor>  ·  </Text>
        <Text dimColor>type </Text>
        <Text color="green">/help</Text>
        <Text dimColor> for commands</Text>
      </Box>

      {/* Config info */}
      <Box flexDirection="column" marginLeft={2} marginTop={1}>
        <Text>
          <Text dimColor>lead      </Text>
          <Text bold color="cyan">{leadName}</Text>
          {'  '}
          <Text dimColor>workers   </Text>
          <Text>{workersStr}</Text>
        </Text>
        <Text>
          <Text dimColor>approval  </Text>
          <Text bold color="yellow">{approvalMode}</Text>
          {'  '}
          <Text dimColor>workspace </Text>
          <Text dimColor>{workspace}</Text>
        </Text>
        <Text>
          <Text dimColor>config    </Text>
          <Text dimColor>{configSource}</Text>
        </Text>
      </Box>

      {/* Divider */}
      <Box marginTop={1} marginLeft={1}>
        <Text dimColor>{'─'.repeat(48)}</Text>
      </Box>
    </Box>
  );
}
