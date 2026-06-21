import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import { router } from "./router";
import { initAuth } from "./api";
import "./styles.css";

// 先取鉴权 token（保证同步的 thumbnailUrl 能带上），再挂载。
async function bootstrap() {
  await initAuth();
  createApp(App).use(createPinia()).use(router).mount("#app");
}

bootstrap();
