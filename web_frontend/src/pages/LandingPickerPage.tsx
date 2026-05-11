import { motion } from "framer-motion";

const cards = [
  { title: "Main dashboard", href: "/dashboard/main", desc: "Guild ops and command analytics." },
  { title: "Economy dashboard", href: "/dashboard/economy", desc: "Accounting, stock, reports and imports." },
];

export function LandingPickerPage() {
  return (
    <div className="mx-auto grid min-h-screen w-full max-w-[1560px] gap-6 p-6">
      <header className="pt-10">
        <h1 className="text-5xl font-medium tracking-tightplus">Albion Analytics</h1>
      </header>
      <div className="grid gap-5 md:grid-cols-2">
        {cards.map((card, index) => (
          <motion.a
            key={card.title}
            href={card.href}
            className="relative min-h-[420px] rounded-shell border border-white/15 bg-white/5 p-8 shadow-glass backdrop-blur-xl2"
            initial={{ y: 56, opacity: 0 }}
            whileInView={{ y: 0, opacity: 1 }}
            transition={{ type: "spring", stiffness: 120, damping: 16, delay: index * 0.1 }}
            whileHover={{ scale: 1.02 }}
          >
            <h2 className="text-3xl font-medium">{card.title}</h2>
            <p className="mt-4 text-apple-muted">{card.desc}</p>
          </motion.a>
        ))}
      </div>
    </div>
  );
}
