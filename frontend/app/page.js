
import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import HowItWorks from "./components/HowItWorks";
import Features from "./components/Features";
import Footer from "./components/Footer";

export default function Home() {
  return (
    <main className="min-h-screen bg-[#070A0D] text-white">
      
      <Navbar />

      <Hero />

      <HowItWorks />

      <Features />

      <Footer />

    </main>
  );
}

