import { PropsWithChildren } from "react";
import { motion } from "framer-motion";

export function AnimatedSection({ children }: PropsWithChildren) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ type: "spring", stiffness: 120, damping: 16 }}
    >
      {children}
    </motion.section>
  );
}
