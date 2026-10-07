# Pooled logistic mixed models of the main study (docs/analysis_plan.md, sections 5 and 7).
#   Rscript scripts/main_glmm.R results/main_long.csv docs/main_glmm.txt
# Input: the long table written by scripts/main_analysis.py --long. Needs lme4 (install.packages("lme4")).
args <- commandArgs(trailingOnly = TRUE)
inp <- if (length(args) >= 1) args[1] else "results/main_long.csv"
out <- if (length(args) >= 2) args[2] else "docs/main_glmm.txt"
suppressPackageStartupMessages(library(lme4))
d <- read.csv(inp, stringsAsFactors = TRUE)
d <- subset(d, condition %in% c("B1", "G1", "G2", "G3", "G4", "R1", "N1R", "N1P2"))
d$condition <- relevel(droplevels(d$condition), ref = "G2")
ctrl <- glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))
sink(out)
cat("## Pooled model: correct ~ condition * model + (1 | pair_id) + (1 | focus_concept)\n")
m1 <- glmer(correct ~ condition * model + (1 | pair_id) + (1 | focus_concept), data = d, family = binomial,
            control = ctrl)
print(summary(m1))
cat("\n## Depth (section 7): G2 vs B1, correct ~ condition * depth + model + random intercepts\n")
dd <- subset(d, condition %in% c("B1", "G2") & !is.na(depth))
dd$condition <- relevel(droplevels(dd$condition), ref = "B1")
m2 <- glmer(correct ~ condition * depth + model + (1 | pair_id) + (1 | focus_concept), data = dd,
            family = binomial, control = ctrl)
print(summary(m2))
sink()
cat("written", out, "\n")
