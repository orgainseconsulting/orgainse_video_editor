import React, {useLayoutEffect} from "react";
import {createRoot} from "react-dom/client";
import {flushSync} from "react-dom";
import {Player} from "@remotion/player";
import {useCurrentFrame} from "remotion";

export function mount(cards) {
  const root = createRoot(document.querySelector("#stage"));
  const player = React.createRef<any>();
  let current;
  const pending = new Map<number, () => void>();
  function Frame() {
    const frame = useCurrentFrame();
    useLayoutEffect(() => {
      window.drawn = frame;
      pending.get(frame)?.();
      pending.delete(frame);
    }, [frame]);
    return React.createElement(current);
  }

  window.openCard = (id, data) => {
    window.sceneData = data;
    const width = data.editable && data.portrait ? 1080 : 1920;
    const height = data.editable ? Math.round(width * window.innerHeight / window.innerWidth) : 1080;
    const [component, frames] = cards[id];
    current = component;
    window.drawn = -1;
    flushSync(() => root.render(<Player key={id} ref={player} component={Frame}
      compositionWidth={width} compositionHeight={height} durationInFrames={frames}
      fps={30} controls={false} autoPlay={false}
      style={{width:"100vw",height:"100vh"}} />));
    return frames;
  };
  window.seekCard = async (frame) => {
    if (window.drawn !== frame) {
      const ready = new Promise<void>(done => pending.set(frame, done));
      player.current.seekTo(frame);
      await ready;
    }
    await Promise.all(Array.from(document.images, im => im.decode()));
  };
}
