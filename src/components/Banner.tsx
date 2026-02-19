import React from 'react';
import { Box, Text } from 'ink';

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
    <Box flexDirection="column" borderStyle="single" borderColor="blue" paddingX={2} paddingY={1} marginBottom={1}>
      <Text bold color="blue">Agent Swarm</Text>
      <Text> </Text>
      <Text><Text dimColor>  Workspace:  </Text><Text>{workspace}</Text></Text>
      <Text><Text dimColor>  Config:     </Text><Text>{configSource}</Text></Text>
      <Text><Text dimColor>  Lead:       </Text><Text bold color="cyan">{leadName}</Text></Text>
      <Text><Text dimColor>  Workers:    </Text><Text>{workersStr}</Text></Text>
      <Text><Text dimColor>  Approval:   </Text><Text bold color="yellow">{approvalMode}</Text></Text>
    </Box>
  );
}
