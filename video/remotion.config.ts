import {Config} from '@remotion/cli/config';
// 自带的 chrome-headless-shell 在这台 Mac 上启动失败，改用系统 Chrome
Config.setBrowserExecutable('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome');
