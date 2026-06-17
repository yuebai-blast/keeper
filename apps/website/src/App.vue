<script setup lang="ts">
import TheHeader from "./sections/TheHeader.vue";
import HeroSection from "./sections/HeroSection.vue";
import PrinciplesSection from "./sections/PrinciplesSection.vue";
import HowItWorksSection from "./sections/HowItWorksSection.vue";
import FeaturesSection from "./sections/FeaturesSection.vue";
import ShowcaseSection from "./sections/ShowcaseSection.vue";
import DownloadSection from "./sections/DownloadSection.vue";
import FaqSection from "./sections/FaqSection.vue";
import TheFooter from "./sections/TheFooter.vue";
</script>

<template>
  <TheHeader />
  <main>
    <HeroSection />
    <PrinciplesSection />
    <HowItWorksSection />
    <FeaturesSection />
    <ShowcaseSection />
    <DownloadSection />
    <FaqSection />
  </main>
  <TheFooter />
</template>
