import { motion } from "framer-motion";

export default function XpPop({ amount, reduce }) {
  if (!amount) {
    return null;
  }
  if (reduce) {
    return <p className="text-sm font-medium text-success">+{amount} XP</p>;
  }
  return (
    <motion.p
      className="text-sm font-medium text-success"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: -4 }}
      transition={{ duration: 0.4 }}
    >
      +{amount} XP
    </motion.p>
  );
}
