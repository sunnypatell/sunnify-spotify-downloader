import type React from 'react';
import ReactPlayer from 'react-player';

export function PlayerYoutube(props: React.ComponentProps<typeof ReactPlayer>) {
  return (
    <ReactPlayer
      controls
      width="100%"
      height="100%"
      {...props}
    />
  );
}