import {Composition} from 'remotion';
import {Main} from './Main';
import {FPS, plan} from './plan';

export const Root = () => (
  <Composition id="Main" component={Main} durationInFrames={plan.total} fps={FPS} width={1920} height={1080} />
);
