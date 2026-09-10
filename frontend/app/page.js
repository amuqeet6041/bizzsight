import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import HowItWorks from "./components/HowItWorks";
import Features from "./components/Features";

export default function Home() {
  return (
    <main className="min-h-screen bg-[#070A0D]">
      <Navbar />
      <Hero />
      <HowItWorks />
      <Features />
    </main>
  );
}